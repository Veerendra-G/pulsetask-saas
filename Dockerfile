FROM nginx:alpine

# Remove default nginx static assets
RUN rm -rf /usr/share/nginx/html/*

# Copy PulseTask React SaaS app
COPY index.html /usr/share/nginx/html/index.html

# Expose port 80
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
