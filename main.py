# -*- coding: utf-8 -*-
import os
import re
import argparse
import sys
import json
from pathlib import Path

import feedparser
import requests
from loguru import logger
from bypy import ByPy
from dotenv import load_dotenv

import aria2p

# 加载环境变量
load_dotenv()

# 初始化全局变量
workspace = Path(os.path.realpath(__file__)).parent
BaiduPan = ByPy()  # 初始化百度网盘实例

# --- 1. 参数解析与配置加载 ---

# 设置命令行参数解析
parser = argparse.ArgumentParser(description="Bangumi Auto Downloader & Syncer")
parser.add_argument("--aria2", action="store_true", help="启用 Aria2 自动下载功能")
args = parser.parse_args()

# 确定配置文件路径
if env_config_path := os.getenv("MTA_CONFIGPATH"):
    logger.info(f"从环境变量加载配置文件: {env_config_path}")
    config_path = Path(env_config_path)
else:
    logger.info("使用默认配置文件路径: .cache/bangumi_config/config.json")
    config_path = Path(".cache/bangumi_config/config.json")

# 加载 Config
if config_path.exists() and config_path.is_file():
    if config_path.suffix == '.json':
        config = json.load(config_path.open(encoding="utf8"))
        logger.info(f"成功加载配置文件: {config_path.as_posix()}")
    else:
        logger.error(f"不支持的配置文件类型: {config_path.name}")
        sys.exit(1)
else:
    logger.error("配置文件未找到或加载失败!")
    sys.exit(1)

# --- 2. 路径与环境设置 ---

# 历史记录文件路径
if history_path_env := os.getenv("MTA_HISTORY_FILE", None):
    history_path = Path(history_path_env)
else:
    history_path = workspace.joinpath(".cache", "bangumi_config", "history.txt")
logger.info(f"使用历史记录文件: {history_path.as_posix()}")
history_path.parent.mkdir(parents=True, exist_ok=True)

# 种子文件保存根目录 (用于同步到网盘)
if async_dir := os.getenv("MTA_TORRENTS_DIR", None):
    async_dir = Path(async_dir)
else:
    async_dir = workspace / "bangumi"
torrent_base_dir = async_dir / "torrents"
logger.info(f"种子文件将保存在: {torrent_base_dir.as_posix()}")
torrent_base_dir.mkdir(parents=True, exist_ok=True)

# 历史记录最大条数
MAX_HISTORY = int(os.getenv("MTA_MAX_HISTORY", max(300, len([f for f in config.get('mikan', []) if f.get('enable', True)]) * 48)))
logger.info(f"最大历史记录条数: {MAX_HISTORY}")

# --- 3. 初始化网络请求 (Session & Proxy) ---

session = requests.session()
if http_proxy := os.getenv("HTTP_PROXY", None):
    session.proxies.update(http=http_proxy)
if https_proxy := os.getenv("HTTPS_PROXY", None):
    session.proxies.update(https=https_proxy)
if proxy := config.get('proxy'):
    session.proxies.update(proxy)

user_agent = os.getenv("MTA_USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36 Edg/114.0.1823.82")
session.headers = {"user-agent": user_agent}

# --- 4. Aria2 初始化 (仅当参数启用时) ---
aria2_client = None
ARIA2_BASE_DIR = ""

if args.aria2:
    logger.info("检测到 --aria2 参数，正在初始化 Aria2 客户端...")
    if "aria2" in config:
        try:
            aria2_client = aria2p.API(aria2p.Client(**config['aria2']))
        except Exception as e:
            logger.error(f"Aria2 连接失败 (Config配置): {e}")
            sys.exit(1)
    else:
        host = os.getenv("MTA_ARIA2_HOST", "localhost")
        port = os.getenv("MTA_ARIA2_PORT", "6800")
        secret = os.getenv("MTA_ARIA2_SECRET", "")
        if host and port:
            try:
                aria2_client = aria2p.API(aria2p.Client(host=host, port=int(port), secret=secret))
            except Exception as e:
                logger.error(f"Aria2 连接失败 (环境变量): {e}")
                sys.exit(1)

    if not aria2_client:
        logger.error("未找到有效的 Aria2 配置，无法启用 Aria2 下载功能。")
        sys.exit(1)

    try:
        # 获取 Aria2 的全局下载路径，用于构建绝对路径
        ARIA2_BASE_DIR = aria2_client.get_global_options().get('dir')
        logger.success(f"Aria2 连接成功，默认下载路径: {ARIA2_BASE_DIR}")
    except Exception as e:
        logger.error(f"无法获取 Aria2 配置信息: {e}")
        sys.exit(1)
else:
    logger.info("未启用 Aria2 下载功能 (仅下载种子并同步)。")

# --- 5. 核心功能函数 ---

def load_history() -> set:
    """加载历史记录"""
    history = set()
    if history_path.exists() and history_path.is_file():
        with history_path.open(encoding='utf8') as f:
            for line in f:
                bang = line.strip()
                if bang:
                    history.add(bang)
    else:
        history_path.touch(exist_ok=True)
    return history

downloaded_history = load_history()
new_items_cache = []

def save_torrent_local(url: str, save_subdir: str, title: str) -> Path | None:
    """
    下载并保存 .torrent 文件到本地目录 (用于网盘同步)。
    返回保存的本地文件路径对象，如果失败返回 None。
    """
    # 清理文件名
    safe_title = re.sub(r'[\\/*?:"<>|]', "_", title)
    filename = f"{safe_title}.torrent"

    # 构造保存路径: 根目录/番剧名/文件名.torrent
    save_path = torrent_base_dir.joinpath(save_subdir, filename)
    save_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        resp = session.get(url)
        resp.raise_for_status()
        save_path.write_bytes(resp.content)
        logger.info(f"种子已保存: {save_path.name}")
        return save_path
    except requests.exceptions.RequestException as e:
        logger.error(f"下载种子文件失败 {url}: {e}")
        return None

def add_task_to_aria2(torrent_url: str, local_torrent_path: Path, save_subdir: str):
    """
    将任务添加到 Aria2。
    优先使用本地已经下载好的种子文件上传给 Aria2 (避免 Aria2 再下载一次种子)。
    """
    if not aria2_client:
        return

    download_options = {'dir': f'{ARIA2_BASE_DIR}/{save_subdir}'}

    try:
        # 尝试使用 XML-RPC 上传本地种子文件
        if local_torrent_path and local_torrent_path.exists():
            aria2_client.add_torrent(local_torrent_path.as_posix(), options=download_options)
            logger.success(f"已推送任务到 Aria2 (本地种子): {local_torrent_path.name}")
        else:
            # 降级：直接投递 URL
            aria2_client.add(torrent_url, options=download_options)
            logger.success(f"已推送任务到 Aria2 (URL): {torrent_url}")
    except Exception as e:
        logger.error(f"推送到 Aria2 失败: {e}")

def get_latest(url: str, rule: str | None = None, savedir: str | None = None):
    """处理单个 RSS Feed"""
    bangumi_cache = set()
    try:
        content = session.get(url).content
    except requests.RequestException as e:
        logger.error(f"RSS 请求失败 {url}: {e}")
        return

    entries = feedparser.parse(content)

    # 确定保存目录名
    if savedir:
        bangumi_name = savedir
    else:
        # 尝试从标题解析，Mikan RSS 标题通常是 "Mikan Project - <Name>"
        feed_title = getattr(entries.feed, 'title', '')
        bangumi_name = feed_title.replace("Mikan Project - ", "").strip()

    for entry in entries['entries']:
        title = str(entry.get('title', '')).strip() if hasattr(entry, 'title') else ""

        # 规则过滤
        if rule and not re.search(rule, title):
            continue

        # 查重
        if title in downloaded_history or title in bangumi_cache:
            continue

        # 寻找种子链接
        download_url = None
        for link in entry['links']:
            if link.get('type') == 'application/x-bittorrent':
                download_url = link['href']
                break

        if isinstance(download_url, str):
            logger.info(f"发现新番剧: {title}")

            # 步骤 1: 始终下载种子到本地 (为了 BaiduPan 同步)
            local_path = save_torrent_local(download_url, bangumi_name, title)

            # 步骤 2: 如果启用了 Aria2，则推送到 Aria2 下载视频
            if args.aria2 and local_path:
                add_task_to_aria2(download_url, local_path, bangumi_name)

            bangumi_cache.add(title)
            new_items_cache.append(title)

    # 更新本次运行的内存历史缓存
    downloaded_history.update(bangumi_cache)

def write_history(lines: list[str]):
    """将新项目写入历史文件顶部"""
    if not lines:
        return

    # 读取旧内容
    old_content = ""
    if history_path.exists():
        with history_path.open(mode='r', encoding='utf8') as r:
            old_content = r.read()

    # 写入新内容 + 旧内容 (截断到 MAX_HISTORY 行)
    new_content_str = '\n'.join(lines[::-1]) # 倒序，最新的在最前
    final_content = new_content_str + '\n' + old_content

    # 简单的行数截断处理
    final_lines = final_content.strip().split('\n')
    if len(final_lines) > MAX_HISTORY:
        final_lines = final_lines[:MAX_HISTORY]

    with history_path.open(mode='w', encoding='utf8') as w:
        w.write('\n'.join(final_lines) + '\n')

@logger.catch
def run():
    logger.info("--- 开始检查更新 ---")

    mikan_list = config.get('mikan', [])
    if not mikan_list:
        logger.warning("配置文件中没有找到 'mikan' 订阅列表。")
        return

    for bangumi in mikan_list:
        if not bangumi.get('enable', True):
            continue

        url = bangumi.get('url')
        rule = bangumi.get('rule') or None
        savedir = bangumi.get('savedir') or None

        if url:
            get_latest(url, rule=rule, savedir=savedir)

    # 如果有新内容，写入历史记录
    if new_items_cache:
        logger.info(f"本次新增 {len(new_items_cache)} 个条目，正在更新历史记录...")
        write_history(new_items_cache)

        # 同步到百度网盘
        logger.info("正在同步种子文件到百度网盘...")
        try:
            # localdir 是本地种子根目录
            # remotedir 是网盘中的目标目录，通常 ByPy 默认在 /apps/bypy/ 下
            # 这里 syncup 会把 torrent_base_dir 下的内容上传到网盘
            BaiduPan.syncup(localdir=str(async_dir))
            logger.success("百度网盘同步完成。")
        except Exception as e:
            logger.error(f"百度网盘同步失败: {e}")
    else:
        logger.info("没有发现新更新。")

if __name__ == '__main__':
    run()
