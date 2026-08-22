#!/bin/bash

#read -p "Enter service name (e.g., Rag or Rag2): " SERVICE_NAME
#read -p "Enter service tag: " SERVICE_TAG

# ---------------------------
# Accept service name and tag from arguments
# ---------------------------
if [[ -z "$1" || -z "$2" ]]; then
    echo "Usage: sudo bash $0 <service_name> <service_tag>"
    exit 1
fi

SERVICE_NAME="$1"
SERVICE_VERSION="$2"
SERVICE_TAG="${SERVICE_NAME}-${SERVICE_VERSION}"  # This will be used for image tag



CHEF_ENV="./chef.env"
COOKBOOKS_DIR="./cookbooks"
SERVICE_COOKBOOK_DIR="$COOKBOOKS_DIR/${SERVICE_NAME}_docker"


# -------------------------
# CHANGED: Resolve paths for validation
# -------------------------
PARENT_DIR=$(dirname "$PWD")
GRANDPARENT_DIR=$(dirname "$PARENT_DIR")
SERVICE_PATH="${GRANDPARENT_DIR}/Subsytems/${SERVICE_NAME}"

# -------------------------
# CHANGED: Check if service directory exists
# -------------------------
if [ ! -d "$SERVICE_PATH" ]; then
    echo "Error: Service '${SERVICE_NAME}' does not exist in Subsytems."
    echo "Path does not exit in Subsytem: $SERVICE_PATH"
    exit 1
fi

# -------------------------
# CHANGED: Check if Dockerfile exists for the service
# -------------------------
DOCKERFILE_PATH="${SERVICE_PATH}/platform/docker/${SERVICE_NAME}/Dockerfile"
if [ ! -f "$DOCKERFILE_PATH" ]; then
    echo " Error: Dockerfile not found for '${SERVICE_NAME}'."
    echo "Expected path: $DOCKERFILE_PATH"
    exit 1
fi

sed -i "s/^DOCKER_IMAGE_TAG=.*/DOCKER_IMAGE_TAG=${SERVICE_TAG}/" "$CHEF_ENV"


PARENT_DIR=$(dirname "$PWD")
GRANDPARENT_DIR=$(dirname "$PARENT_DIR")
#BUILD_CONTEXT="${GRANDPARENT_DIR}"

if [[ "$SERVICE_NAME" == "mcpServer" || "$SERVICE_NAME" == "tts" ]]; then
    BUILD_CONTEXT="${GRANDPARENT_DIR}/Subsytems/${SERVICE_NAME}"
else
    BUILD_CONTEXT="${GRANDPARENT_DIR}"
fi


sed -i "s|^BUILD_CONTEXT=.*|BUILD_CONTEXT=${BUILD_CONTEXT}|" "$CHEF_ENV"


DOCKERFILE_PATH="${GRANDPARENT_DIR}/Subsytems/${SERVICE_NAME}/platform/docker/${SERVICE_NAME}/Dockerfile"
sed -i "s|^DOCKERFILE_PATH=.*|DOCKERFILE_PATH=${DOCKERFILE_PATH}|" "$CHEF_ENV"


mkdir -p "$COOKBOOKS_DIR"

mkdir -p "$SERVICE_COOKBOOK_DIR"


cat > "$SERVICE_COOKBOOK_DIR/metadata.rd" <<EOF
name '${SERVICE_NAME}_docker'
maintainer 'Yashveer'
maintainer_email 'yashveer.dedha@iktara.ai'
license 'All Rights Reserved'
description 'Builds and pushes Django project image to Docker Hub'
version '0.1.0'

depends 'docker'
EOF


cat > "$SERVICE_COOKBOOK_DIR/metadata.json" <<EOF
{
  "name": "${SERVICE_NAME}_docker",
  "description": "Builds and pushes Django project image to Docker Hub",
  "long_description": "",
  "maintainer": "Yashveer",
  "maintainer_email": "yashveer.dedha@iktara.ai",
  "license": "All Rights Reserved",
  "platforms": {},
  "dependencies": {
    "docker": ">= 0.0.0"
  },
  "providing": {},
  "recipes": {},
  "version": "0.1.0",
  "source_url": "",
  "issues_url": "",
  "privacy": false,
  "chef_versions": [],
  "ohai_versions": [],
  "gems": [],
  "eager_load_libraries": true
}
EOF


RECIPES_DIR="$SERVICE_COOKBOOK_DIR/recipes"
mkdir -p "$RECIPES_DIR"

cat > "$RECIPES_DIR/default.rb" <<EORT
#
# Cookbook:: ${SERVICE_NAME}_docker
# Recipe:: default
#

deployment_env_path = "$(realpath "$CHEF_ENV")"

# Parse chef.env
env_vars = {}
if ::File.exist?(deployment_env_path)
  ::File.readlines(deployment_env_path).each do |line|
    next if line.strip.start_with?('#') || line.strip.empty?
    key, value = line.strip.split('=', 2)
    env_vars[key] = value
  end
else
  raise "chef.env file not found at \\#{deployment_env_path}"
end

# Extract variables with validation
dockerfile_path = env_vars['DOCKERFILE_PATH'] or raise "DOCKERFILE_PATH not set in chef.env"
build_context = env_vars['BUILD_CONTEXT'] or raise "BUILD_CONTEXT not set in chef.env"
docker_username = env_vars['DOCKER_USERNAME'] or raise "DOCKER_USERNAME not set in chef.env"
docker_password = env_vars['DOCKER_PASSWORD'] or raise "DOCKER_PASSWORD not set in chef.env"
docker_email = env_vars['DOCKER_EMAIL'] or raise "DOCKER_EMAIL not set in chef.env"
docker_image_tag = env_vars['DOCKER_IMAGE_TAG'] or raise "DOCKER_IMAGE_TAG not set in chef.env"

# Install and start Docker service
docker_service 'default' do
  action [:create, :start]
end

# Build the Docker image using the build context specified in chef.env
execute 'build_rag_docker_image' do
  command "docker build -t #{docker_username}/services:#{docker_image_tag} -f #{dockerfile_path} #{build_context}"
  live_stream true
end

# Authenticate to Docker Hub using docker login
execute 'docker_login' do
  command "docker login -u #{docker_username} -p #{docker_password}"
  live_stream true
end

# Push the built image to Docker Hub
execute 'push_rag_docker_image' do
  command "docker push #{docker_username}/services:#{docker_image_tag}"
  live_stream true
end
EORT


cat > ./Berksfile <<EOF
source 'https://supermarket.chef.io'
# Your main cookbook
cookbook '${SERVICE_NAME}_docker', path: './cookbooks/${SERVICE_NAME}_docker'

# Dependency cookbook
cookbook 'docker', '~> 7.7'
EOF

echo "Chef environment, Berksfile, and cookbook structure updated for service ${SERVICE_NAME} with tag ${SERVICE_TAG}."


if ! chef gem list | grep -q berkshelf; then
    echo "Installing berkshelf gem..."
    chef gem install berkshelf
    echo "berkshelf installed."
fi

echo "Running berks install..."
berks install

echo "Running berks vendor cookbooks..."
berks vendor cookbooks


CHEF_RUN_LIST="${SERVICE_NAME}_docker::default"
echo "Running chef-client for ${CHEF_RUN_LIST}..."
sudo chef-client -z -o "${CHEF_RUN_LIST}"

