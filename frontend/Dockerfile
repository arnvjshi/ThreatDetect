FROM node:20-alpine

WORKDIR /app

# Accept build-time arguments for Next.js env vars (baked at build time)
ARG NEXT_PUBLIC_BACKEND_HTTP_URL=http://localhost:8000
ARG NEXT_PUBLIC_BACKEND_WS_URL=ws://localhost:8000

# Set them as env vars so `next build` sees them
ENV NEXT_PUBLIC_BACKEND_HTTP_URL=$NEXT_PUBLIC_BACKEND_HTTP_URL
ENV NEXT_PUBLIC_BACKEND_WS_URL=$NEXT_PUBLIC_BACKEND_WS_URL

COPY package*.json ./
RUN npm install

COPY . .
RUN npm run build

EXPOSE 3000
CMD ["npm", "run", "start"]
