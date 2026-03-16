

FROM python:3.12-slim

# 基本ツール
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates git bash openssh-client gnupg \
  && rm -rf /var/lib/apt/lists/*

# Google Cloud CLI（公式APTリポジトリ）
RUN echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] http://packages.cloud.google.com/apt cloud-sdk main" \
      > /etc/apt/sources.list.d/google-cloud-sdk.list \
  && curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg \
      | gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg \
  && apt-get update \
  && apt-get install -y --no-install-recommends google-cloud-cli \
  && rm -rf /var/lib/apt/lists/*

# pip を最新版へ
RUN pip install --no-cache-dir --upgrade pip

# gcloud のログ取得で必要になることがある grpcio
RUN pip install --no-cache-dir grpcio

WORKDIR /workspace

CMD ["bash"]