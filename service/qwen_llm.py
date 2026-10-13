import json

from service.llm_service import LLMService

# tokenizer 惰性加载，避免启动时引入 dashscope（约 38MB 内存）
qwen_tokenizer = None

def _get_qwen_tokenizer():
    global qwen_tokenizer
    if qwen_tokenizer is None:
        from dashscope import get_tokenizer
        qwen_tokenizer = get_tokenizer('qwen-coder')
    return qwen_tokenizer

# 通义千问供应商模型接口
# https://bailian.console.aliyun.com/?spm=5176.29597918.nav-v2-dropdown-menu-0.d_main_2_0_0.612a7b086WqU6B&tab=model&scm=20140722.M_10904466._.V_1#/model-market
class QwenLLMService(LLMService):

    # 获取usage
    async def get_usage(self, response, params, answer):
        if response['usage']:
            return await super().get_usage(response, params, answer)
        else:
            query = [msg['content'] for msg in params['messages'] if 'content' in msg]

            # 是否有function
            for item in params.get('tools', []):
                query.append(json.dumps(item, ensure_ascii=False, indent=4))
            query = '\n'.join(query)

            tokenizer = _get_qwen_tokenizer()
            query_token = tokenizer.encode(query)
            answer_token = tokenizer.encode(answer)

            data = {}
            data['prompt_tokens'] = len(query_token)
            data['completion_tokens'] = len(answer_token)
            data['total_tokens'] = data['prompt_tokens'] + data['completion_tokens']
            return data



