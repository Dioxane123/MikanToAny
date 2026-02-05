from multiprocessing import Condition
import sys
import os
import json
from openai import OpenAI
from dotenv import load_dotenv
import argparse
load_dotenv()

class ConfigManager:
    def __init__(self, config_path):
        self.config_path = config_path

    def load_config(self):
        """读取配置文件，如果文件不存在或格式错误则返回初始结构"""
        if not os.path.exists(self.config_path):
            print(f"⚠️ 警告: 配置文件 {self.config_path} 不存在，将创建新文件。")
            return {"mikan": []}

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"❌ 错误: 配置文件 {self.config_path} 格式损坏。")
            sys.exit(1)
        except Exception as e:
            print(f"❌ 读取配置文件失败: {e}")
            sys.exit(1)

    def save_config(self, data):
        """将数据写入配置文件"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(os.path.abspath(self.config_path)), exist_ok=True)

            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            print(f"✅ 配置已成功更新至: {self.config_path}")
        except Exception as e:
            print(f"❌ 写入配置文件失败: {e}")

    def update_entry(self, ai_data):
        """
        核心逻辑：根据 AI 返回的数据更新配置
        1. 如果是 error，直接返回失败
        2. 如果 title 已存在，更新非 default 的字段
        3. 如果 title 不存在，创建新条目（将 default 替换为空字符串或默认值）
        """
        # 1. 检查 AI 是否报错
        if "error" in ai_data:
            print(f"🚫 AI 解析失败: {ai_data['error']}")
            return False

        title = ai_data.get("title")
        if not title or title == "default":
            print("🚫 错误: AI 未能识别出番剧名称 (title)，无法更新。")
            return False

        config_data = self.load_config()
        mikan_list = config_data.get("mikan", [])

        found = False

        # 2. 尝试查找现有条目并更新
        for item in mikan_list:
            if item.get("title") == title:
                found = True
                print(f"🔄 发现已存在的番剧: 【{title}】，正在更新差异项...")
                # 遍历 AI 返回的每个字段，只要不是 "default" 就覆盖
                for key, value in ai_data.items():
                    if value != "default" and key in item:
                        # 只有值不一样才打印日志
                        if item[key] != value:
                            print(f"   - 更新 {key}: {item[key]} -> {value}")
                            item[key] = value
                break

        # 3. 如果没找到，追加新条目
        if not found:
            print(f"🆕 添加新番剧: 【{title}】")
            new_entry = {
                "url": ai_data.get("url") if ai_data.get("url") != "default" else "",
                "title": title,
                "enable": ai_data.get("enable") if ai_data.get("enable") != "default" else True, # 默认为 True
                "savedir": ai_data.get("savedir") if ai_data.get("savedir") != "default" else title, # 默认保存目录同名
                "rule": ai_data.get("rule") if ai_data.get("rule") != "default" else ""
            }
            mikan_list.append(new_entry)

        # 保存回文件
        config_data["mikan"] = mikan_list
        self.save_config(config_data)
        return True

class JsonChat:
    def __init__(self, api_key, model_name="Qwen/Qwen2.5-72B-Instruct"):
        self.client = OpenAI(api_key=api_key, base_url="https://api.siliconflow.cn/v1")
        self.model_name = model_name
        # 注意：开启 JSON 模式时，系统提示词必须包含 "JSON" 字眼

    def ask(self, user_input: str):
        """
        发送消息并获取 JSON 回复
        """
        system_prompt = """你是一个配置管理助手。用户会提供关于番剧下载配置的信息。
        请提取以下字段：
        1. "title": 番剧名字 (必须存在，否则返回 {"error": "未提供番剧名"})
        2. "url": RSS订阅链接
        3. "savedir": 保存文件夹名
        4. "enable": 是否启用 (请根据语义转换为布尔值 true/false，如果用户没说则填 "default")
        5. "rule": 特殊过滤规则

        规则：
        - 对于用户未提及的信息，对应字段的值必须设为字符串 "default"。
        - 最终输出必须是合法的 JSON 对象。
        """
        messages: list[dict[str, str | None]] = [
            {
                "role": "system",
                "content": system_prompt
            }
        ]
        messages.append({"role": "user", "content": user_input})

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                # --- 关键修改：强制输出 JSON 对象 ---
                response_format={"type": "json_object"}
            )

            content = response.choices[0].message.content

            # 记录助手回复，保持上下文
            messages.append({"role": "assistant", "content": content})

            # 尝试直接解析成 Python 字典，方便后续代码使用
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return {"error": "API返回的不是合法JSON", "raw_content": content}

        except Exception as e:
            return {"error": str(e)}

# --- 使用示例 ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MikanToAny修改配置文件")
    parser.add_argument("--prompt", type=str, help="请输入提示词")
    args = parser.parse_args()
    api_key = os.getenv("API_KEY")
    config_path = os.getenv("MTA_CONFIGPATH", ".cache/bangumi_config/config.json")

    bot = JsonChat(api_key=api_key)
    manager = ConfigManager(config_path=config_path)

    print(f"用户请求: {args.prompt}")
    result = bot.ask(args.prompt)

    # 因为我们在 ask 方法里已经 json.loads 了，所以这里直接当字典用
    print("\n--- 解析结果 ---")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    manager.update_entry(result)
