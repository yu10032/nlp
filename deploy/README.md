# 本地持久化部署骨架

新增 `compose.yml`、两个 Dockerfile 和 Nginx 代理。当前电脑未发现 Docker 命令，尚未实际构建容器或在目标服务器验收。

在安装 Docker 的环境中，位于 `work` 执行：

```powershell
docker compose up --build -d
# 可选：导入手工示例
docker compose exec api python -m ta_backend.seed
```

访问 <http://127.0.0.1:8080>。默认只绑定本机，数据库与上传文件持久化在 `data/runtime`，容器重建不覆盖。
后端启动前执行 Alembic 迁移。Nginx 将 `/api` 转发后端，前端其他路由回退 `index.html`。
`.env` 中生成配置通过环境变量传给后端；不把密钥复制进镜像或前端构建。

上线前仍需要课程成员登录与授权、HTTPS、服务器资源测试和外部设备验收。当前课程范围隔离不能代替登录权限。
固定句编码器和 MLP 权重尚未接入，不能宣称这套容器已部署自训模型。
