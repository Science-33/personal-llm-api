import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, field_validator

from utils.util import get_before_timestamp, get_before_month, require_auth, get_before_day, get_current_timestamp
from utils.db_client import db_client

router = APIRouter(prefix="/backend/llm-usage", tags=["backend-llm-usage"])


class ChartBase(BaseModel):
    # 不能为空
    before_num: Optional[str]  # 可选字段
    unit_type: Optional[str]  # 可选字段

    @field_validator('unit_type')
    def validate_unit_type(cls, v):
        """时间单位格式验证"""
        if not v:
            v = 'day'
        if v not in ['day', 'month', 'year']:
            raise ValueError('时间单位必须是day或month或year')
        return v

    @field_validator('before_num')
    def validate_before_num(cls, v):
        """时间范围格式验证"""
        if not v:
            v = '7'
        try:
            v = int(v)
        except ValueError:
            raise ValueError('时间范围必须是整数')

        if v <= 0:
            raise ValueError('时间范围必须大于0')
        return v


def get_chart_params(before_num: Optional[str], unit_type: Optional[str]):
    return ChartBase(before_num=before_num, unit_type=unit_type)

def get_day_params(params):
    xAxis = []
    yAxis = []

    format_str = '%Y-%m-%d'
    for i in range(params.before_num - 1, -1, -1):
        time_stamp = get_before_timestamp(i)
        # 格式化time_stamp时间戳
        xAxis.append(datetime.datetime.fromtimestamp(time_stamp).strftime(format_str))
        yAxis.append(0)
    date_str = get_before_day(params.before_num - 1) + ' 00:00:00'
    search_column_name = 'create_day'

    return xAxis, yAxis, date_str, search_column_name

def get_month_params(params):
    xAxis = []
    yAxis = []
    format_str = '%Y-%m'
    for i in range(params.before_num - 1, -1, -1):
        month_str = get_before_month(i)

        xAxis.append(month_str[:7])
        yAxis.append(0)
    date_str = get_before_month(params.before_num - 1) + ' 00:00:00'
    search_column_name = 'create_month'

    return xAxis, yAxis, date_str, search_column_name

def get_year_params(params):
    xAxis = []
    yAxis = []
    for i in range(params.before_num - 1, -1, -1):
        current_year = get_current_timestamp()[:4]

        xAxis.append(str(int(current_year) - i))
        yAxis.append(0)
    date_str = f'{int(current_year) - params.before_num + 1}-01-01 00:00:00'
    search_column_name = 'create_year'

    return xAxis, yAxis, date_str, search_column_name

# 获取请求次数图表数据
@router.get("/chart-request")
@require_auth
async def chart_request(request: Request, params: ChartBase = Depends(get_chart_params)):

    xAxis = []
    yAxis = []

    if params.unit_type == 'day':
        xAxis, yAxis, date_str, search_column_name = get_day_params(params)

    elif params.unit_type == 'month':
        xAxis, yAxis, date_str, search_column_name = get_month_params(params)

    else:
        xAxis, yAxis, date_str, search_column_name = get_year_params(params)

    sql = f"""
        SELECT {search_column_name}, COUNT(*) AS count
        FROM llm_chat_history
        WHERE create_time >= '{date_str}'
        GROUP BY {search_column_name} order by {search_column_name}
    """

    res = await db_client.select(sql)
    res = [{search_column_name: item[search_column_name], 'count': item['count']} for item in res]

    for item in res:
        index = xAxis.index(item[search_column_name])
        if index != -1:
            yAxis[index] = item['count']

    data = {
        "tooltip": {
            "trigger": 'axis'
        },
        "title": {
            "text": '请求次数',
            "left": 'center',
            "bottom": '0%',
            "textStyle": {
                "fontSize": 14,
                "color": '#666'
            }
        },
        "xAxis": {
            "type": 'category',
            "data": xAxis
        },
        "yAxis": {
            "type": 'value',
            "axisLabel": {
                "formatter": '{value} 次'
            }
        },
        "series": [
            {
                "data": yAxis,
                "type": 'line',
                "smooth": True
            }
        ]
    }

    data = {'status': 0, 'msg': '', 'data': data}
    return data

# 获取token使用图表数据
@router.get("/chart-token")
@require_auth
async def chart_token(request: Request, params: ChartBase = Depends(get_chart_params)):

    xAxis = []
    yAxis_prompt = []
    yAxis_completion = []

    if params.unit_type == 'day':
        format_str = '%Y-%m-%d'
        for i in range(params.before_num - 1, -1, -1):
            time_stamp = get_before_timestamp(i)
            # 格式化time_stamp时间戳
            xAxis.append(datetime.datetime.fromtimestamp(time_stamp).strftime(format_str))
            yAxis_prompt.append(0)
            yAxis_completion.append(0)
        date_str = get_before_day(int(params.before_num) - 1) + ' 00:00:00'
        search_column_name = 'create_day'

    elif params.unit_type == 'month':
        format_str = '%Y-%m'
        for i in range(params.before_num - 1, -1, -1):
            month_str = get_before_month(i)

            xAxis.append(month_str)
            yAxis_prompt.append(0)
            yAxis_completion.append(0)
        date_str = get_before_month(params.before_num - 1) + ' 00:00:00'
        search_column_name = 'create_month'

    else:
        for i in range(params.before_num - 1, -1, -1):
            current_year = get_current_timestamp()[:4]

            xAxis.append(str(int(current_year) - i))
            yAxis_prompt.append(0)
            yAxis_completion.append(0)
        date_str = f'{int(current_year) - params.before_num + 1}-01-01 00:00:00'
        search_column_name = 'create_year'

    sql = f"""
        SELECT {search_column_name}, SUM(prompt_tokens) AS prompt_tokens, SUM(completion_tokens) AS completion_tokens
        FROM llm_chat_history
        WHERE create_time >= '{date_str}'
        GROUP BY {search_column_name} order by {search_column_name}
    """

    res = await db_client.select(sql)
    res = {item[search_column_name]: {'prompt_tokens': item['prompt_tokens'], 'completion_tokens': item['completion_tokens']} for item in res}

    for item in res:
        for i, name in enumerate(xAxis):
            if name in res:
                yAxis_prompt[i] = res[name]['prompt_tokens']
                yAxis_completion[i] = res[name]['completion_tokens']

    data = {
        "tooltip": {
            "trigger": 'axis'
        },
        "legend": {
            "data": ['输入Token', '输出Token']
        },
        "title": {
            "text": 'Token消耗',
            "left": 'center',
            "bottom": '0%',
            "textStyle": {
                "fontSize": 14,
                "color": '#666'
            }
        },
        "xAxis": {
            "type": 'category',
            "data": xAxis
        },
        "yAxis": {
            "type": 'value',
            "axisLabel": {
                "formatter": '{value} token'
            }
        },
        "series": [
            {
                "name": '输入Token',
                "data": yAxis_prompt,
                "type": 'line',
                "smooth": True
            },
            {
                "name": '输出Token',
                "data": yAxis_completion,
                "type": 'line',
                "smooth": True
            }
        ]
    }

    data = {'status': 0, 'msg': '', 'data': data}
    return data

# 获取消费金额图表数据
@router.get("/chart-money")
@require_auth
async def chart_money(request: Request, params: ChartBase = Depends(get_chart_params)):

    xAxis = []
    yAxis = []

    if params.unit_type == 'day':
        xAxis, yAxis, date_str, search_column_name = get_day_params(params)

    elif params.unit_type == 'month':
        xAxis, yAxis, date_str, search_column_name = get_month_params(params)

    else:
        xAxis, yAxis, date_str, search_column_name = get_year_params(params)

    sql = f"""
        SELECT {search_column_name}, SUM(input_price) AS input_price, SUM(output_price) AS output_price
        FROM llm_chat_history
        WHERE create_time >= '{date_str}'
        GROUP BY {search_column_name} order by {search_column_name}
    """

    res = await db_client.select(sql)
    res = {item[search_column_name]: {'price': item['input_price'] + item['output_price']} for item in res}

    for item in res:
        for i, name in enumerate(xAxis):
            if name in res:
                yAxis[i] = f"{res[name]['price']:.6g}"

    data = {
        "tooltip": {
            "trigger": 'axis'
        },
        "title": {
            "text": '消费金额',
            "left": 'center',
            "bottom": '0%',
            "textStyle": {
                "fontSize": 14,
                "color": '#666'
            }
        },
        "xAxis": {
            "type": 'category',
            "data": xAxis
        },
        "yAxis": {
            "type": 'value',
            "axisLabel": {
                "formatter": '{value} 元'
            }
        },
        "series": [
            {
                "data": yAxis,
                "type": 'line',
                "smooth": True
            }
        ]
    }

    data = {'status': 0, 'msg': '', 'data': data}
    return data


# 获取缓存命中token图表数据
@router.get("/chart-cache-token")
@require_auth
async def chart_cache_token(request: Request, params: ChartBase = Depends(get_chart_params)):

    xAxis = []
    yAxis_cache_tokens = []
    yAxis_cache_rate = []

    if params.unit_type == 'day':
        xAxis, yAxis_cache_tokens, date_str, search_column_name = get_day_params(params)

    elif params.unit_type == 'month':
        xAxis, yAxis_cache_tokens, date_str, search_column_name = get_month_params(params)

    else:
        xAxis, yAxis_cache_tokens, date_str, search_column_name = get_year_params(params)

    yAxis_cache_rate = [0] * len(xAxis)

    sql = f"""
        SELECT {search_column_name}, SUM(cache_hit_tokens) AS cache_hit_tokens, SUM(prompt_tokens) AS prompt_tokens
        FROM llm_chat_history
        WHERE create_time >= '{date_str}'
        GROUP BY {search_column_name} order by {search_column_name}
    """

    res = await db_client.select(sql)

    for item in res:
        if item[search_column_name] in xAxis:
            index = xAxis.index(item[search_column_name])
            cache_hit_tokens = item['cache_hit_tokens'] or 0
            prompt_tokens = item['prompt_tokens'] or 0
            yAxis_cache_tokens[index] = cache_hit_tokens
            # 缓存命中率 = 缓存命中的输入token / 总输入token
            yAxis_cache_rate[index] = round(cache_hit_tokens / prompt_tokens * 100, 2) if prompt_tokens else 0

    data = {
        "tooltip": {
            "trigger": 'axis'
        },
        "legend": {
            "data": ['缓存命中Token', '缓存命中率']
        },
        "title": {
            "text": '缓存命中Token',
            "left": 'center',
            "bottom": '0%',
            "textStyle": {
                "fontSize": 14,
                "color": '#666'
            }
        },
        "xAxis": {
            "type": 'category',
            "data": xAxis
        },
        "yAxis": [
            {
                "type": 'value',
                "axisLabel": {
                    "formatter": '{value} token'
                }
            },
            {
                "type": 'value',
                "max": 100,
                "axisLabel": {
                    "formatter": '{value}%'
                }
            }
        ],
        "series": [
            {
                "name": '缓存命中Token',
                "data": yAxis_cache_tokens,
                "type": 'bar'
            },
            {
                "name": '缓存命中率',
                "data": yAxis_cache_rate,
                "type": 'line',
                "smooth": True,
                "yAxisIndex": 1
            }
        ]
    }

    data = {'status': 0, 'msg': '', 'data': data}
    return data

# 获取缓存命中金额图表数据
@router.get("/chart-cache-money")
@require_auth
async def chart_cache_money(request: Request, params: ChartBase = Depends(get_chart_params)):

    xAxis = []
    yAxis = []

    if params.unit_type == 'day':
        xAxis, yAxis, date_str, search_column_name = get_day_params(params)

    elif params.unit_type == 'month':
        xAxis, yAxis, date_str, search_column_name = get_month_params(params)

    else:
        xAxis, yAxis, date_str, search_column_name = get_year_params(params)

    sql = f"""
        SELECT {search_column_name}, SUM(cache_hit_price) AS cache_hit_price
        FROM llm_chat_history
        WHERE create_time >= '{date_str}'
        GROUP BY {search_column_name} order by {search_column_name}
    """

    res = await db_client.select(sql)

    for item in res:
        if item[search_column_name] in xAxis:
            index = xAxis.index(item[search_column_name])
            yAxis[index] = f"{item['cache_hit_price'] or 0:.6g}"

    data = {
        "tooltip": {
            "trigger": 'axis'
        },
        "title": {
            "text": '缓存命中金额',
            "left": 'center',
            "bottom": '0%',
            "textStyle": {
                "fontSize": 14,
                "color": '#666'
            }
        },
        "xAxis": {
            "type": 'category',
            "data": xAxis
        },
        "yAxis": {
            "type": 'value',
            "axisLabel": {
                "formatter": '{value} 元'
            }
        },
        "series": [
            {
                "data": yAxis,
                "type": 'line',
                "smooth": True
            }
        ]
    }

    data = {'status': 0, 'msg': '', 'data': data}
    return data


# 获取按供应商统计的缓存命中图表数据
@router.get("/chart-cache-provider")
@require_auth
async def chart_cache_provider(request: Request, params: ChartBase = Depends(get_chart_params)):

    if params.unit_type == 'day':
        _, _, date_str, _ = get_day_params(params)
    elif params.unit_type == 'month':
        _, _, date_str, _ = get_month_params(params)
    else:
        _, _, date_str, _ = get_year_params(params)

    sql = f"""
        SELECT provider_name, SUM(cache_hit_tokens) AS cache_hit_tokens, SUM(prompt_tokens) AS prompt_tokens, SUM(cache_hit_price) AS cache_hit_price
        FROM llm_chat_history
        WHERE create_time >= '{date_str}' and update_time is not null
        GROUP BY provider_name order by cache_hit_price desc
    """

    res = await db_client.select(sql)

    xAxis = []
    yAxis_price = []
    yAxis_rate = []
    for item in res:
        provider_name = item['provider_name'] or '未知供应商'
        cache_hit_tokens = item['cache_hit_tokens'] or 0
        prompt_tokens = item['prompt_tokens'] or 0

        xAxis.append(provider_name)
        yAxis_price.append(f"{item['cache_hit_price'] or 0:.6g}")
        # 缓存命中率 = 缓存命中的输入token / 总输入token
        yAxis_rate.append(round(cache_hit_tokens / prompt_tokens * 100, 2) if prompt_tokens else 0)

    data = {
        "tooltip": {
            "trigger": 'axis'
        },
        "legend": {
            "data": ['缓存命中金额', '缓存命中率']
        },
        "title": {
            "text": '各供应商缓存命中统计',
            "left": 'center',
            "bottom": '0%',
            "textStyle": {
                "fontSize": 14,
                "color": '#666'
            }
        },
        "xAxis": {
            "type": 'category',
            "data": xAxis
        },
        "yAxis": [
            {
                "type": 'value',
                "axisLabel": {
                    "formatter": '{value} 元'
                }
            },
            {
                "type": 'value',
                "max": 100,
                "axisLabel": {
                    "formatter": '{value}%'
                }
            }
        ],
        "series": [
            {
                "name": '缓存命中金额',
                "data": yAxis_price,
                "type": 'bar'
            },
            {
                "name": '缓存命中率',
                "data": yAxis_rate,
                "type": 'line',
                "smooth": True,
                "yAxisIndex": 1
            }
        ]
    }

    data = {'status': 0, 'msg': '', 'data': data}
    return data


# 获取总使用情况
@router.get("/total-usage")
@require_auth
async def total_usage(request: Request):
    sql = """
        SELECT COUNT(1) AS total_request, SUM(prompt_tokens) AS prompt_tokens, SUM(completion_tokens) AS completion_tokens, SUM(input_price) AS input_price, SUM(output_price) AS output_price, SUM(cache_hit_tokens) AS cache_hit_tokens, SUM(cache_hit_price) AS cache_hit_price
        FROM llm_chat_history where update_time is not null
    """

    res = await db_client.select(sql)
    res = res[0]

    if res['total_request'] != 0:
        total_price = str(round(res['input_price'] + res['output_price'], 2))
        if total_price == '0.0':
            total_price = str(round(res['input_price'] + res['output_price'], 6))

        cache_hit_tokens = res['cache_hit_tokens'] or 0
        cache_hit_price = res['cache_hit_price'] or 0
        total_cache_price = str(round(cache_hit_price, 2))
        if total_cache_price == '0.0':
            total_cache_price = str(round(cache_hit_price, 6))
        # 缓存命中率 = 缓存命中的输入token / 总输入token
        cache_hit_rate = str(round(cache_hit_tokens / res['prompt_tokens'] * 100, 2)) if res['prompt_tokens'] else '0'

        data = {
            'total_request': str(res['total_request']),
            'total_tokens': str(res['prompt_tokens'] + res['completion_tokens']),
            'total_price': total_price,
            'total_cache_tokens': str(cache_hit_tokens),
            'cache_hit_rate': cache_hit_rate,
            'total_cache_price': total_cache_price
        }

    else:
        data = {
            'total_request': '0',
            'total_tokens': '0',
            'total_price': '0.00',
            'total_cache_tokens': '0',
            'cache_hit_rate': '0',
            'total_cache_price': '0.00'
        }

    data = {'status': 0, 'msg': '', 'data': data}
    return data
