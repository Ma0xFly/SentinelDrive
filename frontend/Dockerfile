FROM node:22-alpine

WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1

COPY package*.json ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY . .
ARG NEXT_PUBLIC_API_BASE_URL=/api
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
RUN npm run check && cp -r .next/static .next/standalone/.next/static

EXPOSE 3000
ENV HOSTNAME=0.0.0.0 \
    NODE_ENV=production \
    PORT=3000
CMD ["npm", "run", "start"]
