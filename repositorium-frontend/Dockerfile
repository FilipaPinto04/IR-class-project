FROM node:22-alpine

WORKDIR /app

# Copiar os ficheiros de dependências primeiro para aproveitar a cache do Docker
COPY package.json package-lock.json* ./

# Instalação limpa das dependências diretamente no ambiente Linux do contentor
RUN npm install

# Copiar o resto do código do frontend
COPY . .

# Expor a porta padrão do Vite dev server
EXPOSE 5173

# O Vite precisa da flag --host para comunicar com o exterior do contentor
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]