"""Approved bounded real-provider comparison; no deployment or business tools."""
import json
import os
import subprocess
import time
from urllib.request import urlopen
from openai import OpenAI
from aws_bedrock_token_generator import provide_token
from run_bedrock_smoke import ROOT, BASE, MODEL


def main():
    raw = subprocess.run(['aws', 'configure', 'export-credentials', '--profile',
                          'ai-gateway-lab', '--region', 'us-east-1', '--format', 'process'], capture_output=True, text=True, check=True)
    creds = json.loads(raw.stdout)
    for source, target in [('AccessKeyId','AWS_ACCESS_KEY_ID'),('SecretAccessKey','AWS_SECRET_ACCESS_KEY'),('SessionToken','AWS_SESSION_TOKEN')]:
        os.environ[target] = creds[source]
    os.environ['AWS_REGION'] = os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
    token = provide_token()
    env = os.environ.copy()
    env.update(OPENAI_API_KEY=token, LITELLM_MASTER_KEY='local-synthetic-gateway-only', PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
    private = ROOT/'evidence'/'private'
    private.mkdir(exist_ok=True)
    records = []
    attempts = 0
    result = {'model': MODEL, 'upstream_endpoint': BASE, 'synthetic_only': True,
              'records': records, 'status': 'running', 'automatic_retries': 0,
              'limitations': ['Compatibility smoke only; sample count cannot establish p50/p95.',
                              'Not a Codex CLI end-to-end test or managed gateway policy proof.']}
    def call(client, path, case, **kwargs):
        nonlocal attempts
        if attempts >= 12:
            raise RuntimeError('request_limit')
        attempts += 1
        started = time.perf_counter()
        response = client.responses.create(model=MODEL, max_output_tokens=256, **kwargs)
        if kwargs.get('stream'):
            final = None
            first_text = None
            for event in response:
                if event.type == 'response.output_text.delta' and first_text is None:
                    first_text = (time.perf_counter()-started)*1000
                if event.type == 'response.completed':
                    final = event.response
            response.close()
            response = final
        else:
            first_text = None
        if response is None or response.usage is None:
            raise RuntimeError('usage_unavailable_stop')
        usage = response.usage
        records.append({'path': path, 'case': case, 'status': response.status,
                        'latency_ms': round((time.perf_counter()-started)*1000, 3),
                        'first_text_ms': first_text, 'input_tokens': usage.input_tokens,
                        'output_tokens': usage.output_tokens,
                        'estimated_usd_upper': (usage.input_tokens*.275+usage.output_tokens*1.32)/1e6})
        if sum(row['estimated_usd_upper'] for row in records) >= 4.9:
            raise RuntimeError('budget_stop')
        if response.status != 'completed':
            raise RuntimeError('incomplete_response_stop')
        return response
    log = (private/'bedrock-gateway.log').open('w', encoding='utf-8')
    process = subprocess.Popen([str(ROOT/'.venv'/'Scripts'/'litellm.exe'), '--config',
                                str(ROOT/'litellm.bedrock.yaml'), '--host','127.0.0.1','--port','4002'],
                               env=env, stdout=log, stderr=log)
    try:
        deadline = time.monotonic()+60
        while True:
            if process.poll() is not None or time.monotonic()>deadline:
                raise RuntimeError('gateway_startup_failed')
            try:
                with urlopen('http://127.0.0.1:4002/health/liveliness', timeout=1):
                    break
            except OSError:
                time.sleep(.25)
        for path, endpoint, key in [('direct',BASE,token),('gateway','http://127.0.0.1:4002/v1','local-synthetic-gateway-only')]:
            with OpenAI(base_url=endpoint, api_key=key, max_retries=0, timeout=45) as client:
                first = call(client,path,'text',input='Remember the synthetic code MAPLE73. Reply with exactly LAB_OK.')
                if first.output_text.strip() != 'LAB_OK':
                    raise RuntimeError('text_mismatch')
                continued = call(client,path,'continuation',input='What synthetic code did I give you? Reply with only the code.', previous_response_id=first.id)
                if 'MAPLE73' not in continued.output_text:
                    raise RuntimeError('continuation_semantics_failed')
                streamed = call(client,path,'stream',input='Reply with exactly STREAM_OK.',stream=True)
                if streamed.output_text.strip() != 'STREAM_OK':
                    raise RuntimeError('stream_text_mismatch')
                tool = call(client,path,'tool_call',input='Inspect checkout-api using inspect_service.',tools=[{'type':'function','name':'inspect_service','description':'Read synthetic status','parameters':{'type':'object','properties':{'service':{'type':'string'}},'required':['service'],'additionalProperties':False},'strict':True}],tool_choice={'type':'function','name':'inspect_service'})
                calls = [x for x in tool.output if x.type == 'function_call']
                if len(calls)!=1 or calls[0].name!='inspect_service' or json.loads(calls[0].arguments)!={'service':'checkout-api'}:
                    raise RuntimeError('tool_contract_failed')
                final = call(client,path,'tool_result',previous_response_id=tool.id,input=[{'type':'function_call_output','call_id':calls[0].call_id,'output':'{"status":"healthy","marker":"CEDAR42"}'},{'role':'user','content':'Reply with only the marker from the tool result.'}])
                if 'CEDAR42' not in final.output_text:
                    raise RuntimeError('tool_result_semantics_failed')
        result['status'] = 'passed'
    except Exception as exc:
        result.update(status='stopped', error_type=type(exc).__name__)
        if type(exc) is RuntimeError:
            result['reason'] = str(exc)
        if hasattr(exc,'status_code'):
            result['http_status'] = exc.status_code
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        log.close()
        result.update(attempts=attempts, known_usage_estimated_usd=sum(x['estimated_usd_upper'] for x in records),
                      usage_complete=len(records)==attempts,
                      gateway_process_stopped=process.poll() is not None)
        result['unknown_usage_reserved_usd'] = (attempts-len(records)) * 0.05
        result['reservation_is_not_billed_cost'] = True
        result['recorded_at_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        (ROOT/'evidence'/('bedrock-comparison-'+time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())+'.json')).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
