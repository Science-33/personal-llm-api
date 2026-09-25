
import httpx

# 1. 请求 /v1/models 接口获取可用模型列表
api_key = "sk-6krzNJoef72vmQkzCAf97BFiMwevu2cQ"  # 替换为你的API密钥

response = httpx.get(
    "http://127.0.0.1:2321/v1/models",
    headers={"Authorization": f"Bearer {api_key}"},
)

# 2. 打印所有可用模型的模型名称
result = response.json()
for model in result['data']:
    print(model['id'])
