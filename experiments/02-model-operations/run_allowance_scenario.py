"""Two synthetic workers: ordinary work versus bounded repetitive calls.

Actual LiteLLM policy enforcement, synthetic prices/provider, no paid inference.
The bare direct control deliberately has no application spending guard.
"""
import json
import subprocess
import time
import run_policy_controls as policy

ROOT = policy.ROOT
PREFIX = 'fieldlab02-allowance'
IMAGE = 'ghcr.io/berriai/litellm@sha256:c8756e7b9a61fe45df2ccb5b781d388c3b2f3a21ef9e4956630caef20f9f03aa'
policy.PREFIX = PREFIX
docker, api = policy.docker, policy.api


def request_payload(worker):
    return {'model':'synthetic-codex','input':'Synthetic '+worker+' incident review',
            'max_output_tokens':16}


def direct(worker):
    # This process has synthetic input only and runs inside our provider container.
    code = ('import urllib.request,json; p='+repr(request_payload(worker))+'; '
            "r=urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:4010/v1/responses',"
            "data=json.dumps(p).encode(),headers={'Content-Type':'application/json'}));"
            "b=json.load(r);print(json.dumps({'http_status':r.status,'usage':b['usage']}))")
    return json.loads(docker('exec',PREFIX+'-provider','/app/.venv/bin/python','-c',code))


def main():
    (ROOT/'evidence'/'private').mkdir(parents=True,exist_ok=True)
    result={'synthetic_only':True,'prices_are_synthetic':True,'status':'stopped',
            'budget_per_key':0.05,'cost_per_completed_call':0.013,'max_output_tokens':16,
            'repetitive_calls_planned':8,'ordinary_calls_planned':3,'trials':[],
            'direct_control':'bare API without an application or provider per-key budget'}
    created=[]
    network=False
    try:
        if docker('ps','-a','--filter','name='+PREFIX,'--format','{{.Names}}'):
            raise RuntimeError('owned_names_already_exist')
        docker('network','create',PREFIX);network=True
        docker('run','-d','--name',PREFIX+'-db','--network',PREFIX,'--network-alias','db',
               '-e','POSTGRES_PASSWORD=synthetic-local-only','-e','POSTGRES_DB=litellm',
               'postgres@sha256:00bc86618629af00d2937fdc5a5d63db3ff8450acf52f0636ec813c7f4902929')
        created.append(PREFIX+'-db')
        docker('run','-d','--name',PREFIX+'-provider','--network',PREFIX,'--network-alias','provider',
               '-v',str(ROOT)+':/lab:ro','--entrypoint','/app/.venv/bin/python',IMAGE,'/lab/policy_provider.py')
        created.append(PREFIX+'-provider')
        docker('run','-d','--name',PREFIX+'-gateway','--network',PREFIX,'-p','127.0.0.1:4003:4000',
               '-v',str(ROOT/'litellm.policy.yaml')+':/app/config.yaml:ro',
               '-e','LITELLM_MASTER_KEY='+policy.KEY,
               '-e','DATABASE_URL=postgresql://postgres:synthetic-local-only@db:5432/litellm',
               IMAGE,'--config','/app/config.yaml','--port','4000')
        created.append(PREFIX+'-gateway')
        deadline=time.monotonic()+120
        while time.monotonic()<deadline:
            try:
                if api('/health/readiness')[0]==200: break
            except (OSError,ValueError): pass
            time.sleep(1)
        else: raise RuntimeError('readiness_timeout')
        result['image_digest']=IMAGE
        for trial_number in range(1,4):
            trial={'trial':trial_number,'direct':[],'gateway':[]}
            result['trials'].append(trial)
            keys={}
            for worker in ('ordinary','repetitive'):
                status,body=api('/key/generate',{'key_alias':f'{worker}-{trial_number}',
                    'models':['synthetic-codex'],'max_budget':0.05,'budget_duration':'1h'})
                if status!=200: raise RuntimeError('key_creation_failed')
                keys[worker]=body['key']
            schedule=['ordinary']+['repetitive']*4+['ordinary']+['repetitive']*4+['ordinary']
            for worker in schedule:
                before=policy.provider_count()
                observed=direct(worker)
                observed.update(worker=worker,provider_calls=policy.provider_count()-before)
                trial['direct'].append(observed)
            for worker in schedule:
                before=policy.provider_count()
                started=time.monotonic()
                status,body=api('/v1/responses',request_payload(worker),keys[worker])
                row={'worker':worker,'http_status':status,
                     'provider_calls':policy.provider_count()-before,
                     'elapsed_ms':round((time.monotonic()-started)*1000,2)}
                if status==200: row['usage']=body.get('usage')
                else:
                    error=body.get('error',{})
                    row['error_class']='budget' if 'budget' in str(error).lower() else 'other'
                trial['gateway'].append(row)
        # Observe persistence, not merely the immediate request log.
        deadline=time.monotonic()+120
        while True:
            result['accounting']=policy.database_evidence()
            rows=result['accounting']['identities']
            reconciled=len(rows)==6 and all(abs(r['key_spend']-r['logged_spend'])<1e-8 for r in rows)
            if reconciled or time.monotonic()>=deadline: break
            time.sleep(10)
        result['counters_reconciled']=reconciled
        result['summary']=[]
        for trial in result['trials']:
            for worker in ('ordinary','repetitive'):
                baseline=[r for r in trial['direct'] if r['worker']==worker]
                gated=[r for r in trial['gateway'] if r['worker']==worker]
                result['summary'].append({'trial':trial['trial'],'worker':worker,
                    'direct_completed':sum(r['http_status']==200 for r in baseline),
                    'gateway_completed':sum(r['http_status']==200 for r in gated),
                    'gateway_rejected':sum(r['http_status']!=200 for r in gated),
                    'direct_synthetic_cost':round(sum(r['http_status']==200 for r in baseline)*.013,3),
                    'gateway_synthetic_cost':round(sum(r['http_status']==200 for r in gated)*.013,3)})
        result['status']='observed'
    except Exception as exc:
        result['error_type']=type(exc).__name__
        if isinstance(exc,RuntimeError):result['reason']=str(exc)
    finally:
        private=ROOT/'evidence'/'private'
        for name in reversed(created):
            logs=subprocess.run(['docker','logs',name],capture_output=True,text=True,encoding='utf-8',errors='replace')
            (private/(name+'.log')).write_text(logs.stdout+logs.stderr,encoding='utf-8')
            docker('rm','-f','-v',name)
        if network:docker('network','rm',PREFIX)
        result['containers_remaining']=docker('ps','-a','--filter','name='+PREFIX,'--format','{{.Names}}')
        name='allowance-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'.json'
        (ROOT/'evidence'/name).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'evidence':name,'status':result['status'],'summary':result.get('summary'),
              'reconciled':result.get('counters_reconciled'),'remaining':result['containers_remaining'],
              'error_type':result.get('error_type'),'reason':result.get('reason')},indent=2))


if __name__=='__main__':main()
