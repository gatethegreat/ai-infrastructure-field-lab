"""Bounded actual Codex client test; isolated synthetic filesystem, Bedrock via LiteLLM."""
import json
import os
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from aws_bedrock_token_generator import provide_token
from run_bedrock_smoke import ROOT, MODEL

records=[]
lock=threading.Lock()
KEY='local-synthetic-gateway-only'


class BoundedRelay(BaseHTTPRequestHandler):
    def log_message(self,*args): pass

    def do_POST(self):
        size=int(self.headers.get('Content-Length','0'))
        if self.path!='/v1/responses' or size>100000 or self.headers.get('Authorization')!='Bearer '+KEY:
            self.send_error(403); return
        payload=json.loads(self.rfile.read(size))
        with lock:
            if len(records)>=4:
                self.send_error(429); return
            record={'attempt':len(records)+1,'request_bytes':size}
            records.append(record)
        payload['max_output_tokens']=256
        payload['model']=MODEL
        started=time.monotonic()
        request=Request('http://127.0.0.1:4002/v1/responses',data=json.dumps(payload).encode(),headers={
            'Authorization':'Bearer '+KEY,'Content-Type':'application/json'})
        try:
            with urlopen(request,timeout=60) as response:
                data=response.read()
                status=response.status
                content_type=response.headers.get('Content-Type','application/json')
            (ROOT/'evidence'/'private'/('codex-response-'+str(record['attempt'])+'.txt')).write_bytes(data)
            record['content_type']=content_type
            record['response_bytes']=len(data)
            # Buffering deliberately changes stream delivery; this is not a latency test.
            for line in data.decode().splitlines():
                if not line.startswith('data: '): continue
                try: event=json.loads(line[6:])
                except ValueError: continue
                if event.get('error'):
                    error=event['error']
                    record['stream_error_code']=str(error.get('code','unknown'))
                    message=error.get('message','')
                    record['stream_error_class']=('capacity_exceeded' if 'Exceeded on-demand capacity' in message
                        else 'unsupported_web_search' if 'web search is not supported' in message else 'other')
                final=event.get('response',{})
                if final.get('usage'):
                    record['usage']=final['usage']
                    record['response_status']=final.get('status')
        except HTTPError as exc:
            status=exc.code; data=exc.read(); content_type='application/json'
        except Exception as exc:
            status=502;data=b'{"error":{"message":"bounded relay upstream failure"}}';content_type='application/json'
            record['error_type']=type(exc).__name__
        record.update(http_status=status,elapsed_ms=round((time.monotonic()-started)*1000,2))
        self.send_response(status)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    result={'synthetic_only':True,'model':MODEL,'records':records,'max_requests':4,
            'max_output_tokens_per_request':256,'stream_buffering':True,'status':'stopped'}
    raw=subprocess.run(['aws','configure','export-credentials','--profile','ai-gateway-lab','--region','us-east-1','--format','process'],capture_output=True,text=True,check=True)
    creds=json.loads(raw.stdout)
    for source,target in [('AccessKeyId','AWS_ACCESS_KEY_ID'),('SecretAccessKey','AWS_SECRET_ACCESS_KEY'),('SessionToken','AWS_SESSION_TOKEN')]:
        os.environ[target]=creds[source]
    os.environ['AWS_REGION']=os.environ['AWS_DEFAULT_REGION']='us-east-1'
    token=provide_token()
    env=os.environ.copy()
    env.update(OPENAI_API_KEY=token,LITELLM_MASTER_KEY=KEY,PYTHONUTF8='1',PYTHONIOENCODING='utf-8')
    private=ROOT/'evidence'/'private'
    log=(private/'codex-bedrock-gateway.log').open('w',encoding='utf-8')
    gateway=subprocess.Popen([str(ROOT/'.venv'/'Scripts'/'litellm.exe'),'--config',str(ROOT/'litellm.bedrock.yaml'),'--host','127.0.0.1','--port','4002'],env=env,stdout=log,stderr=log)
    relay=ThreadingHTTPServer(('127.0.0.1',4004),BoundedRelay)
    threading.Thread(target=relay.serve_forever,daemon=True).start()
    container='fieldlab02-codex-task'
    created=False
    try:
        deadline=time.monotonic()+60
        while time.monotonic()<deadline:
            try:
                with urlopen('http://127.0.0.1:4002/health/liveliness',timeout=1): break
            except OSError: time.sleep(.5)
        else: raise RuntimeError('gateway_readiness_timeout')
        if subprocess.run(['docker','ps','-a','--filter','name=^/'+container+'$','--format','{{.Names}}'],capture_output=True,text=True,check=True).stdout.strip():
            raise RuntimeError('container_name_already_owned')
        args=['docker','run','--name',container,'--cap-drop=ALL','--security-opt=no-new-privileges',
              '--read-only','--tmpfs','/root/.codex','--tmpfs','/tmp',
              '-v',str(ROOT/'fixtures'/'codex-business')+':/lab:ro','-e','LAB_GATEWAY_KEY='+KEY,
              'fieldlab02-codex:0.153.4','exec','--ignore-user-config','--ephemeral','--skip-git-repo-check',
              '--sandbox','danger-full-access','--json','-c','project_doc_max_bytes=0',
              '-c','web_search="disabled"','-c','features.multi_agent=false',
              '-c','model_provider="fieldlab"','-m',MODEL,
              '-c','model_providers.fieldlab={name="Field lab",base_url="http://host.docker.internal:4004/v1",env_key="LAB_GATEWAY_KEY",wire_api="responses",request_max_retries=0,stream_max_retries=0}',
              'Read /lab/incident.json using a shell command. Then give a business owner one sentence with the failure percentages before and after rollback. This is synthetic data in an externally isolated read-only container. Do not change files or use network tools. Keep every message and tool call brief.']
        created=True
        started=time.monotonic()
        run=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180)
        (private/'codex-task.jsonl').write_text(run.stdout,encoding='utf-8')
        (private/'codex-task-stderr.log').write_text(run.stderr,encoding='utf-8')
        result.update(exit_code=run.returncode,task_elapsed_ms=round((time.monotonic()-started)*1000,2))
        items=[]
        for line in run.stdout.splitlines():
            try: items.append(json.loads(line))
            except ValueError: pass
        completed=[x.get('item',{}) for x in items if x.get('type')=='item.completed']
        messages=[x.get('text','') for x in completed if x.get('type')=='agent_message']
        result['final_answer']=messages[-1] if messages else ''
        result['successful_file_read']=any(x.get('type')=='command_execution' and x.get('exit_code')==0 and 'failed_requests' in x.get('aggregated_output','') for x in completed)
        result['answer_contains_expected_percentages']='7.5%' in result['final_answer'] and '0.5%' in result['final_answer']
        if run.returncode==0 and result['successful_file_read'] and result['answer_contains_expected_percentages']:
            result['status']='passed'
    except Exception as exc:
        result['error_type']=type(exc).__name__
        if isinstance(exc,RuntimeError): result['reason']=str(exc)
    finally:
        if created:
            subprocess.run(['docker','rm','-f','-v',container],capture_output=True,check=False)
        relay.shutdown();relay.server_close()
        gateway.terminate()
        try: gateway.wait(timeout=10)
        except subprocess.TimeoutExpired: gateway.kill();gateway.wait()
        log.close()
        result['known_usage_estimated_usd']=sum((r['usage']['input_tokens']*.275+r['usage']['output_tokens']*1.32)/1e6 for r in records if r.get('usage'))
        result['unknown_usage_reserved_usd']=sum(.05 for r in records if not r.get('usage'))
        result['gateway_process_stopped']=gateway.poll() is not None
        result['container_remaining']=subprocess.run(['docker','ps','-a','--filter','name=^/'+container+'$','--format','{{.Names}}'],capture_output=True,text=True,check=True).stdout.strip()
        path=ROOT/'evidence'/('codex-task-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'.json')
        path.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(result,indent=2))


if __name__=='__main__':main()
