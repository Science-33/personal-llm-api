
import json

from fastapi import APIRouter, Depends, Request

from utils.util import require_auth, PaginationParams, get_page_params
from utils.db_client import db_client

router = APIRouter(prefix="/backend/chat", tags=["chat"])

@router.get("/chat-history")
@require_auth
async def chat_history(request: Request, params: PaginationParams = Depends(get_page_params)):
    # 分页查询

    sql = f"""SELECT * FROM llm_chat_history ORDER BY id DESC LIMIT {(params.page - 1) * params.perPage},{params.perPage}"""

    data_list = await db_client.select(sql)

    res = []
    i = -1
    for item in data_list:
        i += 1
        res.append(item)

        item['prompt'] = (item['prompt'] or '')[:40] + '...'
        item['id'] = i + 1 + (params.page - 1) * params.perPage

        if item['update_time'] is None:
            # 请求未完成（上游报错或流式被中断），只记录了 prompt 和 context
            item['status'] = '未完成'
            item['duration'] = '-'
            item['total_price'] = '-'
            item['prompt_tokens'] = '-'
            item['completion_tokens'] = '-'
        else:
            item['status'] = '成功'
            item['total_price'] = (item['input_price'] or 0) + (item['output_price'] or 0)
            item['input_price'] = "{0:.15f}".format(item['input_price'] or 0).rstrip('0').rstrip('.')
            item['output_price'] = "{0:.15f}".format(item['output_price'] or 0).rstrip('0').rstrip('.')

            item['prompt_tokens'] = f"{item['prompt_tokens'] or 0} ⋙ {item['completion_tokens'] or 0}"
            item['completion_tokens'] = f"{item['completion_tokens'] or 0} / {item['output_price']}元"
            item['total_price'] = f"{item['total_price']:.6g} 元"
            if item['create_time']:
                item['duration'] = str(int((item['update_time'] - item['create_time']).total_seconds())) + ' s'
        item['create_time'] = item['create_time'].strftime('%Y-%m-%d %H:%M:%S')

        item['context'] = json.loads(item['context'])
        item['context'].append({'role': 'assistant', 'content': item['answer'] or '（该请求未完成，未收到模型回复）'})

        for context_item in item['context']:
            if 'content' in context_item and context_item['content']:
                if '<think>' in context_item['content']:
                    context_item['content'] = context_item['content'].replace('<think>', '\n## <think>\n').replace('</think>', '\n## </think>\n')

                # 处理多模态
                if isinstance(context_item['content'], list):
                    context_list = []
                    for obj in context_item['content']:
                        if 'text' in obj:
                            context_list.append(obj['text'])
                        elif 'image_url' in obj:
                            context_list.append(f'![image]({obj["image_url"]["url"]})')
                    context_item['content'] = '\n\n\n'.join(context_list)

            elif 'tool_calls' in context_item:
                context_item['content'] = json.dumps(context_item['tool_calls'], ensure_ascii=False, indent=4)
            elif 'function' in context_item:
                context_item['role'] = 'function'
                context_item['content'] = json.dumps(context_item['function'], ensure_ascii=False, indent=4)

    sql = 'select count(1) as cou from llm_chat_history'
    total = await db_client.select(sql)
    total = total[0]['cou']

    data = {'status':0, 'msg':'', 'data':{'count':total, 'rows':res}}
    return data


@router.post("/chat-history/clear")
@require_auth
async def chat_history_clear(request: Request):
    # 先统计条数，用于返回清空数量
    sql = 'select count(1) as cou from llm_chat_history'
    total = await db_client.select(sql)
    total = total[0]['cou']

    if total:
        await db_client.execute('DELETE FROM llm_chat_history')

    return {"status": 0, "msg": f"已清空 {total} 条请求数据", "data": {}}

