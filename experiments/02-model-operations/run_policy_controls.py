"""Real LiteLLM policy tests with synthetic provider prices; no paid calls."""
import json
from pathlib import Path
import subprocess
import time
import argparse
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parent
PREFIX = 'fieldlab02-policy'
IMAGE = 'ghcr.io/berriai/litellm:v1.100.0'
KEY = 'local-synthetic-policy-only'


def docker(*args):
    return subprocess.run(['docker', *args], capture_output=True, text=True, encoding='utf-8', errors='replace', check=True).stdout.strip()


def api(route, payload=None, key=KEY):
    request = Request('http://127.0.0.1:4003'+route,
                      data=json.dumps(payload).encode() if payload is not None else None,
                      headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
    try:
        with urlopen(request, timeout=30) as response:
            return response.status,json.loads(response.read())
    except HTTPError as exc:
        return exc.code,json.loads(exc.read())


def provider_count():
    return json.loads(docker('exec', PREFIX+'-provider', '/app/.venv/bin/python', '-c',
        "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:4010/stats').read().decode())"))['requests']


def database_evidence():
    # Return only selected synthetic aliases and aggregates, never tokens or raw records.
    query = '''SELECT coalesce(json_agg(t), '[]'::json) FROM (
      SELECT v.key_alias, v.spend AS key_spend, v.max_budget,
        count(s.request_id) AS logged_requests,
        coalesce(sum(s.spend),0) AS logged_spend,
        coalesce(sum(s.prompt_tokens),0) AS input_tokens,
        coalesce(sum(s.completion_tokens),0) AS output_tokens
      FROM "LiteLLM_VerificationToken" v
      LEFT JOIN "LiteLLM_SpendLogs" s ON s.api_key=v.token
      GROUP BY v.key_alias,v.spend,v.max_budget ORDER BY v.key_alias) t;'''
    rows = json.loads(docker('exec', PREFIX+'-db', 'psql', '-U', 'postgres', '-d', 'litellm', '-tAc', query))
    canary_query = '''SELECT count(*) FROM "LiteLLM_SpendLogs" s
      WHERE row_to_json(s)::text LIKE '%SYNTHETIC_LOG_CANARY%';'''
    details_query = '''SELECT coalesce(json_agg(t), '[]'::json) FROM (
      SELECT v.key_alias,s.status,s.spend,s.prompt_tokens,s.completion_tokens
      FROM "LiteLLM_SpendLogs" s JOIN "LiteLLM_VerificationToken" v ON s.api_key=v.token
      ORDER BY v.key_alias,s."startTime") t;'''
    return {'identities': rows, 'request_accounting': json.loads(docker(
        'exec',PREFIX+'-db','psql','-U','postgres','-d','litellm','-tAc',details_query)),
        'rows_containing_prompt_canary': int(docker(
        'exec', PREFIX+'-db','psql','-U','postgres','-d','litellm','-tAc',canary_query))}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--settle-before-restart',action='store_true')
    args=parser.parse_args()
    result = {'synthetic_only':True,'prices_are_synthetic':True,'checks':[], 'status':'running'}
    result['settle_before_restart']=args.settle_before_restart
    created=[]
    network=False
    try:
        # Refuse to touch an existing run's resources.
        existing=docker('ps','-a','--filter','name='+PREFIX,'--format','{{.Names}}')
        if existing:
            raise RuntimeError('owned_names_already_exist')
        result['image_digest']=docker('image','inspect',IMAGE,'--format','{{index .RepoDigests 0}}')
        docker('network','create',PREFIX)
        network=True
        docker('run','-d','--name',PREFIX+'-db','--network',PREFIX,'--network-alias','db',
               '-e','POSTGRES_PASSWORD=synthetic-local-only','-e','POSTGRES_DB=litellm','postgres:17.6')
        created.append(PREFIX+'-db')
        docker('run','-d','--name',PREFIX+'-provider','--network',PREFIX,'--network-alias','provider',
               '-v',str(ROOT)+':/lab:ro','--entrypoint','/app/.venv/bin/python',IMAGE,
               '/lab/policy_provider.py')
        created.append(PREFIX+'-provider')
        docker('run','-d','--name',PREFIX+'-gateway','--network',PREFIX,'-p','127.0.0.1:4003:4000',
               '-v',str(ROOT/'litellm.policy.yaml')+':/app/config.yaml:ro',
               '-e','LITELLM_MASTER_KEY='+KEY,'-e','DATABASE_URL=postgresql://postgres:synthetic-local-only@db:5432/litellm',
               IMAGE,'--config','/app/config.yaml','--port','4000')
        created.append(PREFIX+'-gateway')
        deadline=time.monotonic()+120
        while time.monotonic()<deadline:
            try:
                status,_=api('/health/readiness')
                if status==200:
                    break
            except (OSError, ValueError):
                pass
            time.sleep(1)
        else:
            raise RuntimeError('gateway_readiness_timeout')
        keys={}
        for alias,budget in [('team-a',0.02),('team-b',1.0),('burst',0.02),('rate',1.0)]:
            payload={'key_alias':alias,'models':['synthetic-codex'],'max_budget':budget,'budget_duration':'1h'}
            if alias=='rate': payload['rpm_limit']=1
            status,body=api('/key/generate',payload)
            if status!=200 or not body.get('key'):
                raise RuntimeError('key_creation_failed')
            keys[alias]=body['key']
        for case,alias,model in [('allowed','team-a','synthetic-codex'),('forbidden_model','team-a','forbidden-model')]:
            status,body=api('/v1/responses',{'model':model,'input':'SYNTHETIC_LOG_CANARY'},keys[alias])
            result['checks'].append({'case':case,'http_status':status,'provider_requests':provider_count()})
        # Allow asynchronous spend writes to settle before the next phase.
        time.sleep(15)
        for attempt in range(4):
            status,_=api('/v1/responses',{'model':'synthetic-codex','input':'SYNTHETIC_LOG_CANARY'},keys['team-a'])
            result['checks'].append({'case':'budget_probe','attempt':attempt+1,'http_status':status,'provider_requests':provider_count()})
            if status!=200:
                break
            time.sleep(15)
        status,_=api('/v1/responses',{'model':'synthetic-codex','input':'SYNTHETIC_LOG_CANARY'},keys['team-b'])
        result['checks'].append({'case':'other_identity_after_budget','http_status':status,'provider_requests':provider_count()})
        for attempt in range(2):
            status,_=api('/v1/responses',{'model':'synthetic-codex','input':'synthetic rate probe'},keys['rate'])
            result['checks'].append({'case':'rate_probe','attempt':attempt+1,'http_status':status,'provider_requests':provider_count()})
        def burst_request(_):
            return api('/v1/responses',{'model':'synthetic-codex','input':'synthetic concurrent budget probe'},keys['burst'])[0]
        with ThreadPoolExecutor(max_workers=4) as pool:
            result['concurrent_budget_http_statuses']=list(pool.map(burst_request,range(4)))
        if args.settle_before_restart: time.sleep(75)
        result['accounting_before_restart']=database_evidence()
        docker('restart',PREFIX+'-gateway')
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            try:
                status,_=api('/health/readiness')
                if status==200: break
            except (OSError,ValueError): pass
            time.sleep(1)
        status,_=api('/v1/responses',{'model':'synthetic-codex','input':'restart probe'},keys['team-a'])
        result['checks'].append({'case':'budget_after_restart','http_status':status,'provider_requests':provider_count()})
        result['accounting_before_outage']=database_evidence()
        docker('stop',PREFIX+'-provider')
        started=time.monotonic()
        status,_=api('/v1/responses',{'model':'synthetic-codex','input':'synthetic outage probe'},keys['team-b'])
        result['checks'].append({'case':'provider_stopped','http_status':status,'elapsed_ms':round((time.monotonic()-started)*1000,2)})
        docker('start',PREFIX+'-provider')
        time.sleep(3)
        started=time.monotonic()
        status,_=api('/v1/responses',{'model':'synthetic-codex','input':'synthetic recovery probe'},keys['team-b'])
        result['checks'].append({'case':'provider_restored','http_status':status,'elapsed_ms':round((time.monotonic()-started)*1000,2)})
        time.sleep(75)
        result['accounting_after_recovery']=database_evidence()
        status,_=api('/v1/responses',{'model':'synthetic-codex','input':'synthetic settled burst probe'},keys['burst'])
        result['checks'].append({'case':'burst_budget_after_settlement','http_status':status})
        result['status']='observed'
    except Exception as exc:
        result['status']='stopped'
        result['error_type']=type(exc).__name__
        if isinstance(exc,RuntimeError): result['reason']=str(exc)
    finally:
        private=ROOT/'evidence'/'private'
        private.mkdir(exist_ok=True)
        for name in reversed(created):
            logs=subprocess.run(['docker','logs',name],capture_output=True,text=True,encoding='utf-8',errors='replace')
            (private/(name+'.log')).write_text(logs.stdout+logs.stderr,encoding='utf-8')
            if name.endswith('-gateway'):
                result['gateway_console_contains_prompt_canary']='SYNTHETIC_LOG_CANARY' in logs.stdout+logs.stderr
            docker('rm','-f','-v',name)
        if network: docker('network','rm',PREFIX)
        result['containers_remaining']=docker('ps','-a','--filter','name='+PREFIX,'--format','{{.Names}}')
        path=ROOT/'evidence'/('policy-controls-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'.json')
        path.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(result,indent=2))


if __name__=='__main__': main()
