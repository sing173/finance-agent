# 自定义构建镜像：在 node:22-bullseye 基础上预装 OHOS 工具链 + JDK + git
# 用途：finance-agent 的 HAP 构建链（prepare_hap / build_backend / build_frontend / build_pack）
#
# 构建方式（在你的 Linux 构建服务器，/data/command-line-tools 已存在时执行）：
#   mkdir -p /data/ohos-build/command-line-tools
#   cp -r /data/command-line-tools/. /data/ohos-build/command-line-tools/
#   cp <本仓库>/docker/ohos-build/Dockerfile /data/ohos-build/Dockerfile
#   cd /data/ohos-build
#   docker build -t 192.168.1.172:5001/ohos-build:latest .
#   docker push 192.168.1.172:5001/ohos-build:latest
# 注意：/data/ohos-build/command-line-tools 体积很大，切勿提交进 git（仓库 .gitignore 已忽略）。

FROM 192.168.1.172:5001/node:22-bullseye

# 1) 系统依赖：git（克隆兄弟工程）、JDK17（hvigorw 构建必须）、curl（Release 删除等）
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      git openjdk-17-jdk curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# 2) OHOS 工具链：从构建上下文 ./command-line-tools 拷入镜像
#    （布局保持与宿主机 /data/command-line-tools 一致：
#      hnpcli  -> sdk/default/openharmony/toolchains/hnpcli
#      hvigorw -> bin/hvigorw 或 hvigor/bin/hvigorw
#      ohpm    -> bin/ohpm 或 ohpm/bin/ohpm）
COPY command-line-tools /opt/command-line-tools

# 3) 环境变量：让 common.sh 的 detect_* 通过 COMMAND_LINE_TOOLS 与 PATH 找到三个工具，并配好 JDK
ENV COMMAND_LINE_TOOLS=/opt/command-line-tools
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH="/opt/command-line-tools/bin:/opt/command-line-tools/hvigor/bin:/opt/command-line-tools/ohpm/bin:/opt/command-line-tools/sdk/default/openharmony/toolchains:${JAVA_HOME}/bin:${PATH}"

# 4) 保险：确保可执行位（COPY 一般会保留，这里兜底）
RUN chmod +x \
      /opt/command-line-tools/bin/* \
      /opt/command-line-tools/hvigor/bin/* \
      /opt/command-line-tools/ohpm/bin/* \
      /opt/command-line-tools/sdk/default/openharmony/toolchains/hnpcli \
      2>/dev/null || true

# 5) 校验关键工具均在 PATH
RUN command -v hnpcli \
 && command -v hvigorw \
 && command -v ohpm \
 && command -v java \
 && command -v git \
 && command -v node \
 && echo "ohos-build image ready"
