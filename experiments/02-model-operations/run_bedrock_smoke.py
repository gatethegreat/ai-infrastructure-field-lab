"""Bounded paid Responses smoke. Credentials remain in process memory."""
import json
import os
from pathlib import Path
import subprocess
import time

from aws_bedrock_token_generator import provide_token
from openai import OpenAI, APIStatusError

ROOT = Path(__file__).resolve().parent
BASE = 'https://bedrock-runtime.us-east-1.amazonaws.com/openai/v1'
MODEL = 'us.openai.gpt-5.6-luna'


def main():
    # CLI exports into captured memory only; never print credential output.
    raw = subprocess.run(['aws', 'configure', 'export-credentials', '--profile',
                          'ai-gateway-lab', '--region', 'us-east-1', '--format', 'process'],
                         capture_output=True, text=True, check=True)
    credentials = json.loads(raw.stdout)
    for source, target in [('AccessKeyId', 'AWS_ACCESS_KEY_ID'),
                           ('SecretAccessKey', 'AWS_SECRET_ACCESS_KEY'),
                           ('SessionToken', 'AWS_SESSION_TOKEN')]:
        os.environ[target] = credentials[source]
    os.environ['AWS_REGION'] = 'us-east-1'
    os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
    token = provide_token()
    client = OpenAI(api_key=token, base_url=BASE, max_retries=0, timeout=45)
    result = {'model': MODEL, 'endpoint': BASE, 'synthetic_only': True,
              'max_output_tokens': 256, 'attempts': 1,
              'price_source': 'https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-openai-gpt-56-luna.html',
              'input_usd_per_million': 0.275, 'output_usd_per_million': 1.32}
    started = time.perf_counter()
    try:
        response = client.responses.create(model=MODEL, input='Reply with exactly LAB_OK.',
                                           max_output_tokens=256)
        result.update(status=response.status, expected_text=response.output_text.strip() == 'LAB_OK',
                      latency_ms=round((time.perf_counter()-started)*1000, 3))
        if response.usage is None:
            result['usage_unavailable'] = True
        else:
            result['input_tokens'] = response.usage.input_tokens
            result['output_tokens'] = response.usage.output_tokens
            result['estimated_usd_upper'] = (response.usage.input_tokens*0.275 + response.usage.output_tokens*1.32)/1_000_000
    except APIStatusError as exc:
        # Error messages may contain account details; retain only classification.
        result.update(status='http_error', http_status=exc.status_code,
                      error_type=type(exc).__name__, usage_unavailable=True)
        body = exc.body if isinstance(exc.body, dict) else {}
        message = str(body).lower()
        result['classification'] = ('access_denied' if 'access' in message and 'denied' in message
                                    else 'model_or_endpoint_error')
    finally:
        client.close()
    (ROOT/'evidence'/'bedrock-smoke.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
