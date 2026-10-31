# milvus-lite (Docker)

把 [Milvus Lite](https://milvus.io/docs/milvus_lite.md) 打包成一个**独立 gRPC 服务**的 Docker 镜像，
支持 `linux/amd64` 与 `linux/arm64`，可直接 `docker compose up` 或从 Docker Hub 拉取：

```bash
docker pull kennytian/milvus-lite:3.2.2
```

已发布 tag：`3.2.2` / `3.2` / `3` / `latest`（均为 amd64 + arm64 的 manifest list），
以及分架构的 `3.2.2-amd64` / `3.2.2-arm64`。

---

## 1. 先纠正原方案里的几个硬伤

| 原方案写法 | 实际行为 | 结论 |
| --- | --- | --- |
| `CMD ["milvus-server", "--proxy-port", "19530", "--data", "/data/milvus.db"]` | `milvus-server` 是 **milvus-lite 2.x** 的命令。3.x（当前文档版本，milvus-lite 3.2.2）只提供 `milvus-lite` 命令，子命令是 `milvus-lite server`，参数为 `--data-dir / --host / --port / --max-workers`。镜像里根本没有 `milvus-server`，容器会直接 `executable file not found`。 | 必须换成 3.x 的 CLI |
| `--data /data/milvus.db`（单文件） | 3.x 的存储引擎变了：`.db` 只是**目录名**，里面是 `collections/`、`LOCK`、`databases/` 等。2.x 的 `.db` 文件 3.x **原地打不开**。 | 挂载目录，不要挂单文件 |
| `EXPOSE 19530` + 端口映射 | 3.x 的服务默认就绑 `0.0.0.0:19530`（`DEFAULT_HOST = "0.0.0.0"`），端口映射可用；但 **只有 gRPC，没有 REST API**（`curl :19530` 不会响应 HTTP）。 | 客户端用 pymilvus，不要用 REST |
| 无鉴权直接映射 `19530:19530` | Milvus Lite 不支持认证 / 用户 / RBAC / TLS，官方明确要求「不要暴露到不可信网络」。 | 默认只绑 `127.0.0.1` |
| `restart: always` | 用户主动 `docker stop` 后还会被拉起。 | 建议 `unless-stopped` |
| `version: '3.8'` | Compose v2 已废弃该字段，会打印 warning。 | 去掉 |
| `deploy.resources.limits` | Compose v2 是支持的（非 Swarm 也生效），可以保留；但 0.5 CPU 在批量建索引/导入时偏紧，默认给 1.0。 | 保留可调 |

另外一个 2.x 的坑：milvus-lite 2.x 只发布 macOS / linux **x86_64** 的 wheel，`linux/arm64` 根本装不上。
3.2.2 是 **纯 Python 包**（`py3-none-any`），依赖 `faiss-cpu / pyarrow / grpcio / numpy` 均有 aarch64 wheel，
所以多架构构建不需要交叉编译，也不需要 QEMU 跑安装脚本。

---

## 2. 快速开始

```bash
git clone <this-repo> && cd milvus-lite

# 方式 A：用已发布镜像
docker compose pull && docker compose up -d      # 或 docker compose up -d --build 本地构建

# 方式 B：本地构建
docker compose up -d --build
```

检查状态：

```bash
docker compose ps                 # healthy 表示 gRPC 端口已就绪
docker compose logs -f milvus-lite
```

客户端（**必须用 pymilvus 3.x**，与服务端同代）：

```bash
python -m pip install "pymilvus==3.0.2"
```

```python
from pymilvus import MilvusClient

client = MilvusClient(uri="http://127.0.0.1:19530")   # 远程方式，不是本地 .db 路径
client.create_collection("demo", dimension=384)
client.insert("demo", [{"id": 1, "vector": [0.1] * 384, "text": "hello"}])
print(client.search("demo", data=[[0.1] * 384], limit=1, output_fields=["text"]))
```

> 注意 `MilvusClient("http://127.0.0.1:19530")` 走网络；`MilvusClient("./x.db")` 走进程内本地库。
> 两者不能混用：容器内那个数据目录被容器进程用 `flock` 独占，宿主机上的 pymilvus 不要去读同一个目录。

---

## 3. 目录结构

```
milvus-lite/
├── Dockerfile            # 两阶段构建，非 root 运行，多架构
├── entrypoint.sh         # 修正 /data 属主 + gosu 降权 + 环境变量拼参数
├── docker-compose.yml
├── requirements.txt      # pymilvus==3.0.2 / milvus-lite==3.2.2
├── .env.example
└── data/                 # 数据持久化目录（挂载到容器 /data）
```

## 4. 配置项

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `MILVUS_LITE_DATA_DIR` | `/data` | 数据目录（目录，不是文件） |
| `MILVUS_LITE_HOST` | `0.0.0.0` | 容器内监听地址；改成 `127.0.0.1` 则只有容器内可连 |
| `MILVUS_LITE_PORT` | `19530` | 容器内 gRPC 端口 |
| `MILVUS_LITE_BIND_ADDR` | `127.0.0.1` | **宿主机**发布地址，`0.0.0.0` 才对局域网开放 |
| `MILVUS_LITE_HOST_PORT` | `19530` | 宿主机发布端口 |
| `MILVUS_LITE_IMAGE` | `kennytian/milvus-lite:3.2.2` | compose 使用/构建的镜像名 |

`docker-compose.yml` 里的资源限制：

```yaml
deploy:
  resources:
    limits:
      cpus: "1.0"
      memory: 1G
```

内存跟向量量级强相关（HNSW 全内存），数据大了先把 `memory` 调上去，或者客户端改用 `IVF_FLAT/SQ8`。

## 5. 多架构构建与推送

```bash
# 需要先 docker login
docker buildx create --name milvus-builder --use 2>/dev/null || docker buildx use milvus-builder

docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t kennytian/milvus-lite:3.2.2 \
  -t kennytian/milvus-lite:3.2 \
  -t kennytian/milvus-lite:3 \
  -t kennytian/milvus-lite:latest \
  --push .
```

自检：

```bash
docker buildx imagetools inspect kennytian/milvus-lite:3.2.2
```

### 5.1 本机实测的兜底做法（buildx 拉不到 registry 时）

如果宿主网络的 `auth.docker.io` 只能走代理（直连 IPv6 超时），`buildx build --push` 会在
`failed to fetch oauth token` 上卡死——BuildKit 的 registry client 不吃 `HTTP(S)_PROXY`。
这时用「老 builder 分架构构建 + daemon 推送 + 合成 manifest」：

```bash
# 先确保本地有对应架构的 base image（daemon 走它自己的代理，能拉）
docker pull --platform linux/amd64 python:3.12-slim-bookworm
docker pull --platform linux/arm64 python:3.12-slim-bookworm

DOCKER_BUILDKIT=0 docker build --platform linux/amd64 -t kennytian/milvus-lite:3.2.2-amd64 .
DOCKER_BUILDKIT=0 docker build --platform linux/arm64 -t kennytian/milvus-lite:3.2.2-arm64 .

docker push kennytian/milvus-lite:3.2.2-amd64
docker push kennytian/milvus-lite:3.2.2-arm64

# docker manifest 走 CLI 自己的网络，需要显式给代理
export HTTPS_PROXY=http://127.0.0.1:7890
docker manifest create kennytian/milvus-lite:3.2.2 \
  --amend kennytian/milvus-lite:3.2.2-amd64 \
  --amend kennytian/milvus-lite:3.2.2-arm64
docker manifest push kennytian/milvus-lite:3.2.2

# 别名 tag：imagetools 可以直接复制 manifest list，不用重推 layer
for t in 3.2 3 latest; do
  docker buildx imagetools create -t kennytian/milvus-lite:$t kennytian/milvus-lite:3.2.2
done
```

> 老 builder 的一个坑：`--platform linux/arm64` 只影响拉哪个 base image，构建时按 tag 解析到本地
> 现存的镜像。所以每次构建前先 `docker pull --platform <目标架构>`，否则会报
> `image ... was found but its platform (linux/amd64) does not match the specified platform (linux/arm64)`。

## 6. 备份与迁移

数据就是这个目录，直接 `tar` 即可（**先 `docker compose stop`**，否则 `LOCK` 里的进程会继续写）：

```bash
docker compose stop
tar czf milvus-lite-data-$(date +%F).tgz data/
docker compose start
```

迁去正式版 Milvus / Zilliz Cloud，用官方 dump 工具导出成 BulkWriter JSON：

```bash
docker compose run --rm --entrypoint sh milvus-lite -c \
  'pip install "pymilvus[bulk_writer]==3.0.2" && milvus-lite dump -d /data -c demo -p /data/export'
```

## 7. 已知限制（Milvus Lite 3.2.2 本身，不是镜像问题）

- **单进程独占**：一个数据目录同一时刻只能被一个进程持有（`flock` 保护），所以 `replicas` 只能是 1，也不能多容器共享同一卷。
- **无认证 / 无 TLS / 无 RBAC**：不要映射到公网。
- **只有 gRPC**：没有 REST / `/v2/vectordb/...` 接口，Attu 等 GUI 可能只能部分功能可用。
- **RPC 子集**：不支持的接口返回 `UNIMPLEMENTED`；不支持 schema 变更、partition 级 load/release。
- **并发写同一 collection 不安全**：读并发没问题，写请串行。
- **不支持**：BINARY / FLOAT16 / BFLOAT16 / INT8 向量、PQ 类索引。
- 适合本地开发、边缘设备、小规模场景；生产请用 Milvus Standalone / Distributed 或 Zilliz Cloud。

## 8. 镜像细节

- 基础镜像 `python:3.12-slim-bookworm`，两阶段构建，运行时无编译工具链。
- 非 root 运行（uid/gid `10001`），`entrypoint.sh` 在启动时把 `/data` 的属主修正后再 `gosu` 降权（Linux 上 bind mount 目录默认是 root，否则会写不进去）。
- `tini` 做 PID 1，`STOPSIGNAL SIGINT`：Milvus Lite 只在收到 SIGINT 时才优雅退出（排空在途 RPC、关闭 DB、释放 `LOCK`），收到 SIGTERM 会被直接杀掉。
- 内置 `HEALTHCHECK`：TCP 探活 `127.0.0.1:${MILVUS_LITE_PORT}`。
