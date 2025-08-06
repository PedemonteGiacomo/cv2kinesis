# Multi-stage build for React admin application
FROM node:18-alpine AS build

# Set working directory
WORKDIR /app

# Accept build arguments for React environment variables
ARG REACT_APP_USER_POOL_ID
ARG REACT_APP_USER_POOL_CLIENT_ID
ARG REACT_APP_AWS_REGION
ARG REACT_APP_API_BASE_URL

# Set environment variables from build arguments
ENV REACT_APP_USER_POOL_ID=${REACT_APP_USER_POOL_ID}
ENV REACT_APP_USER_POOL_CLIENT_ID=${REACT_APP_USER_POOL_CLIENT_ID}
ENV REACT_APP_AWS_REGION=${REACT_APP_AWS_REGION}
ENV REACT_APP_API_BASE_URL=${REACT_APP_API_BASE_URL}
ENV REACT_APP_ENVIRONMENT=production

# Debug: Print environment variables during build
RUN echo "Build-time environment variables:" && \
    echo "REACT_APP_USER_POOL_ID=${REACT_APP_USER_POOL_ID}" && \
    echo "REACT_APP_USER_POOL_CLIENT_ID=${REACT_APP_USER_POOL_CLIENT_ID}" && \
    echo "REACT_APP_AWS_REGION=${REACT_APP_AWS_REGION}" && \
    echo "REACT_APP_API_BASE_URL=${REACT_APP_API_BASE_URL}"

# Copy package files
COPY package*.json ./

# Install dependencies (including dev dependencies for build)
RUN npm install

# Copy source code
COPY . .

# Build the application
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built application from build stage
COPY --from=build /app/build /usr/share/nginx/html

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 80
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
