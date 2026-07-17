FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

EXPOSE 5173

# --host is required so the Vite dev server is reachable from outside the container
CMD ["npm", "run", "dev", "--", "--host"]
