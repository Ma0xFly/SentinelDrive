# 多阶段构建：Node 构建静态产物，nginx 托管
FROM node:22-alpine AS build

WORKDIR /app
ENV PNPM_HOME=/pnpm
ENV PATH=$PNPM_HOME:$PATH

RUN corepack enable

COPY pnpm-lock.yaml pnpm-workspace.yaml package.json ./
# allowBuilds 配置在 pnpm-workspace.yaml 中，pnpm fetch 需要它来识别可运行的依赖构建脚本
RUN pnpm fetch

COPY . .
# max build 产物为 dist/ 下的静态文件（含按路由预渲染的 index.html）
RUN pnpm install --offline && pnpm build

FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 3000