# Usar imagen oficial de Node.js
FROM node:18-alpine

# Establecer directorio de trabajo
WORKDIR /app

# Copiar package.json y package-lock.json
COPY package*.json ./

# Instalar dependencias
RUN npm ci --only=production

# Copiar aplicación
COPY . .

# Crear directorio para salida
RUN mkdir -p /app/output_stories

# Exponer puerto
EXPOSE 3100

# Comando para iniciar la aplicación
CMD ["node", "app.js"]
