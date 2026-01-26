<div align="center">

# Mikan to Any

获取蜜柑计划的RSS链接，将最新的种子文件同步到百度网盘或者利用Aria2下载。
</div>

---

**改自[Mikan to Aria2](https://github.com/Taokyla/MikanToAria2)**
原本是做成插件给bot用，但是由于服务器即将到期且找不到合适的替代所以姑且做一个独立版用于个人追番用。
bypy在使用时需要登录，自行搜索教程解决。使用百度网盘的原因主要是他有无敌的离线下载，在早期如果磁力请求的文件在网盘内可以找到就几乎是秒入盘，现在好像没这个功能了，可惜。
## 使用方法
1. 创建项目对应环境
```bash
pip install -r requirements.txt
```
2. 修改[env_template.txt](https://github.com/Dioxane123/MikanToAny/blob/master/env_template.txt)中环境变量对应值，留空即使用默认值。部分环境变量解释如下：
```
MTA_CONFIGPATH: 配置文件路径，默认".cache/bangumi_config/config.json"
MTA_HISTORY_FILE: 历史记录文件路径".cache/bangumi_config/history.txt"
MTA_TORRENTS_DIR: 种子下载目录。种子文件会下载到"$MTA_TORRENTS_DIR/bangumi"目录下，网盘会同步"$MTA_TORRENTS_DIR"目录(即同步"bangumi"文件夹)
MTA_MAX_HISTORY: 最大历史记录数
MTA_USER_AGENT: 访问RSS链接时使用的浏览器头
HTTP_PROXY: 访问RSS链接时的代理设置
HTTPS_PROXY: 访问RSS链接时的代理设置
MTA_ARIA2_HOST: Aria2的rpc主机地址，默认"localhost"
MTA_ARIA2_PORT: Aria2的端口，默认"6800"
MTA_ARIA2_SECRET: Aria2的rpc密钥，默认为空
```
3. 修改[env_template.txt](https://github.com/Dioxane123/MikanToAny/blob/master/env_template.txt)的文件名为`.env`
```bash
mv env_template.txt .env
```
4. 创建你的配置文件并放到你的配置文件路径下。示例如下：
```json
{
    "mikan": [
        {
            "url": "https://mikanime.tv/RSS/Bangumi?bangumiId=3583&subgroupid=370",
            "title": "直至魔女消逝",
            "enable": true,
            "rule": "",
            "savedir": "直至魔女消逝"
        }
    ]
}
```
5. 运行代码，添加`--aria2`表示同步网盘且使用Aria2下载种子链接，不添加此项则仅同步网盘。
```bash
source venv/bin/activate
python main.py --aria2
```
## 未来更新计划
[ ] - 合适的方法交互更新配置文件，现在手写配置文件有点蠢。
> 本来是在QQ上和bot聊天修改配置文件的，可惜服务器过期了qwq

以下原README
---


<div align="center">

# Mikan to Aria2

读取蜜柑计划的rss订阅，下载最新的动画！

</div>

---

**需要 python > 3.10**

海象运算符 yes! `:=`

以前用树莓派的时候写的小脚本，现在我已经不用了。

## 推荐

[Auto_Bangumi](https://github.com/EstrellaXD/Auto_Bangumi) 基于 [Mikan Project](https://mikanani.me)、[qBittorrent](https://qbittorrent.org) 的全自动追番整理下载工具。只需要在 [Mikan Project](https://mikanani.me) 上订阅番剧，就可以全自动追番。并且整理完成的名称和目录可以直接被 [Plex]()、[Jellyfin]() 等媒体库软件识别，无需二次刮削。

## 使用方式

- 修改`config/config.default.yml`，重命名为`config.yml`保存到`config`文件夹下

- 或者: 使用环境变量`MTA_CONFIGPATH`指定配置文件，支持yml和json

- 给脚本加个crontab定时执行，例如：

```
*/30 * * * * python MikanToAria2/main.py
```

## 环境变量

- `MTA_CONFIGPATH` 配置文件路径，默认为`config/config.yml`
- `MTA_HISTORY_FILE` 指定历史保存文件路径
- `MTA_TORRENTS_DIR` 种子保存文件夹，默认为`torrents`
- `MTA_MAX_HISTORY` 最大加载历史记录，默认为300
- `MTA_USER_AGENT` 使用的user-agent
- `HTTP_PROXY` & `HTTPS_PROXY` 代理地址
- `MTA_ARIA2_HOST`,`MTA_ARIA2_PORT`,`MTA_ARIA2_SECRET` aria2配置

### config.yml 说明 (json也行)

#### aria2 (可选)

- `host` 你的aria2的rpc链接地址

- `port` rpc端口，默认为6800

- `secret` rpc密码

#### proxy (可选)

- `http` 一般是`http://127.0.0.1:1080`，socks5可以用`'socks5://127.0.0.1:1080'`

- `https` 同上，前缀是https,也可以用`'socks5://127.0.0.1:1080'`

#### mikan `list[dict, ...]`，每项含有以下key组成的字典

- `url` rss订阅链接，例如：https://mikanani.me/RSS/Bangumi?bangumiId=2359&subgroupid=370

- `rule` 可选，正则匹配，会匹配title，符合的才会下载

- `savedir` 可选，动画的保存路径，默认为番名

### Tip

ubuntu 使用ssr

```shell
sudo apt update
sudo apt install shadowsocks-libev
ss-local -s youserverip -p youserverport -k youserverpasswd -m aes-256-gcm -l 1080 -b 127.0.0.1 &
```
