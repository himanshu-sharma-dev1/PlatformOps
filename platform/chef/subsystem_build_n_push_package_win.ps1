Param(
  [string]$ServiceName = $(Read-Host "Enter service name (e.g., Rag or Rag2)"),
  [string]$ServiceTag  = $(Read-Host "Enter service tag")
)

function Remove-BomIfPresent {
  param([Parameter(Mandatory)] [string]$Path)
  if (!(Test-Path -LiteralPath $Path)) { return }
  try {
    $bytes = [System.IO.File]::ReadAllBytes($Path)
    if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
      [System.IO.File]::WriteAllBytes($Path, $bytes[3..($bytes.Length-1)])
    }
  } catch { }
}

function Write-FileUtf8NoBom {
  param(
    [Parameter(Mandatory)][string]$Path,
    [Parameter(Mandatory)][string]$Content
  )
  $dir = Split-Path -Path $Path -Parent
  if ($dir -and !(Test-Path -LiteralPath $dir)) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
  }
  # Write as UTF8 first (may include BOM depending on host)
  $Content | Set-Content -LiteralPath $Path -Encoding UTF8
  # Strip BOM if present
  Remove-BomIfPresent -Path $Path
}

# === Paths ===
$Here            = Get-Location
$ParentDir       = Split-Path -Path $Here -Parent
$ChefEnv         = Join-Path $ParentDir "chef\chef.env"
$CookbooksDir    = Join-Path $Here "cookbooks"
$ServiceCbName   = "{0}_docker" -f $ServiceName
$ServiceCbDir    = Join-Path $CookbooksDir $ServiceCbName
$RecipeDir       = Join-Path $ServiceCbDir "recipes"
$GrandParentDir  = Split-Path -Path $ParentDir -Parent

# Adjust if your repo uses "Subsystems" not "Subsytems"
$BuildContext    = Join-Path $GrandParentDir ("Subsytems\{0}" -f $ServiceName)
$DockerfilePath  = Join-Path $GrandParentDir ("Subsytems\{0}\platform\docker\{0}\Dockerfile" -f $ServiceName)

# === Ensure chef.env exists ===
if (!(Test-Path $ChefEnv)) {
  New-Item -ItemType Directory -Path (Split-Path $ChefEnv -Parent) -Force | Out-Null
  New-Item -ItemType File -Path $ChefEnv -Force | Out-Null
}

# === Helper: upsert key=value in chef.env, preserving comments ===
function Set-EnvKV {
  param([string]$File, [string]$Key, [string]$Value)
  $lines = @()
  if (Test-Path $File) {
    $raw = Get-Content -LiteralPath $File -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
    if ($null -ne $raw) { $lines = $raw -split "`r?`n" }
  }
  $pattern = "^{0}=" -f [regex]::Escape($Key)
  $found = $false
  for ($i=0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match $pattern) {
      $lines[$i] = "$Key=$Value"
      $found = $true
    }
  }
  if (-not $found) { $lines += "$Key=$Value" }
  $out = ($lines -join "`r`n")
  Write-FileUtf8NoBom -Path $File -Content $out
}

# === Update env values ===
Set-EnvKV -File $ChefEnv -Key "DOCKER_IMAGE_TAG" -Value $ServiceTag
Set-EnvKV -File $ChefEnv -Key "BUILD_CONTEXT"     -Value $BuildContext
Set-EnvKV -File $ChefEnv -Key "DOCKERFILE_PATH"   -Value $DockerfilePath

# === Create cookbook structure ===
New-Item -ItemType Directory -Path $CookbooksDir -Force | Out-Null
New-Item -ItemType Directory -Path $ServiceCbDir  -Force | Out-Null
New-Item -ItemType Directory -Path $RecipeDir     -Force | Out-Null

# === metadata.rb ===
$metadataRb = @"
name '${ServiceCbName}'
maintainer 'Yashveer'
maintainer_email 'yashveer.dedha@iktara.ai'
license 'All Rights Reserved'
description 'Builds and pushes Django project image to Docker Hub'
version '0.1.0'
"@
Write-FileUtf8NoBom -Path (Join-Path $ServiceCbDir "metadata.rb") -Content $metadataRb

# === metadata.json ===
$metadataJson = @"
{
  "name": "${ServiceCbName}",
  "description": "Builds and pushes Django project image to Docker Hub",
  "maintainer": "Yashveer",
  "maintainer_email": "yashveer.dedha@iktara.ai",
  "license": "All Rights Reserved",
  "version": "0.1.0",
  "dependencies": {}
}
"@
Write-FileUtf8NoBom -Path (Join-Path $ServiceCbDir "metadata.json") -Content $metadataJson

# === recipes/default.rb (no docker_service; docker CLI only) ===
$defaultRb = @"
#
# Cookbook:: ${ServiceCbName}
# Recipe:: default
#

deployment_env_path = "$($ChefEnv -replace '\\','\\\\')"
puts "Deployment env path: \#{deployment_env_path}"

env_vars = {}
if ::File.exist?(deployment_env_path)
  ::File.readlines(deployment_env_path).each do |line|
    next if line.strip.start_with?('#') || line.strip.empty?
    key, value = line.strip.split('=', 2)
    env_vars[key] = value
  end
else
  raise "chef.env file not found at \#{deployment_env_path}"
end

dockerfile_path   = env_vars['DOCKERFILE_PATH']   or raise "DOCKERFILE_PATH not set in chef.env"
build_context     = env_vars['BUILD_CONTEXT']     or raise "BUILD_CONTEXT not set in chef.env"
docker_username   = env_vars['DOCKER_USERNAME']   or raise "DOCKER_USERNAME not set in chef.env"
docker_password   = env_vars['DOCKER_PASSWORD']   or raise "DOCKER_PASSWORD not set in chef.env"
docker_email      = env_vars['DOCKER_EMAIL']      or raise "DOCKER_EMAIL not set in chef.env"
docker_image_tag  = env_vars['DOCKER_IMAGE_TAG']  or raise "DOCKER_IMAGE_TAG not set in chef.env"

execute 'check_docker' do
  command 'docker version'
  live_stream true
end

execute 'build_image' do
  command "docker build -t #{docker_username}/services:#{docker_image_tag} -f \"#{dockerfile_path}\" \"#{build_context}\""
  live_stream true
end

execute 'docker_login' do
  command "docker login -u \"#{docker_username}\" -p \"#{docker_password}\""
  sensitive true
  live_stream true
end

execute 'push_image' do
  command "docker push #{docker_username}/services:#{docker_image_tag}"
  live_stream true
end

"@
Write-FileUtf8NoBom -Path (Join-Path $RecipeDir "default.rb") -Content $defaultRb

# === Berksfile (no docker dependency) ===
$berksfile = @"
source 'https://supermarket.chef.io'
cookbook '${ServiceCbName}', path: './cookbooks/${ServiceCbName}'
"@
Write-FileUtf8NoBom -Path (Join-Path $Here "Berksfile") -Content $berksfile

Write-Host "=== Running berks install... ==="
berks install
if ($LASTEXITCODE -ne 0) { Write-Error "berks install failed"; exit 1 }

Write-Host "=== Running berks vendor cookbooks... ==="
berks vendor cookbooks
if ($LASTEXITCODE -ne 0) { Write-Error "berks vendor failed"; exit 1 }

Write-Host "=== Running chef-client (local mode)... ==="
$ChefRunList = "${ServiceCbName}::default"
chef-client -z -o "$ChefRunList"
