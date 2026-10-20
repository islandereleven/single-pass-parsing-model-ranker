IMAGE ?= single-pass-parsing-model-ranker:local
IMAGE_TAG ?= $(shell git rev-parse --short=12 HEAD)
DOCKER_PLATFORM ?= linux/amd64
ECR_REPOSITORY_URL ?=
ECR_REGISTRY = $(firstword $(subst /, ,$(ECR_REPOSITORY_URL)))
ECR_REGION = $(word 4,$(subst ., ,$(ECR_REGISTRY)))
ECR_IMAGE = $(ECR_REPOSITORY_URL):$(IMAGE_TAG)

.PHONY: build-image smoke-image push-image

build-image:
	docker build --tag $(IMAGE) .

smoke-image: build-image
	docker run --rm $(IMAGE) --help
	docker run --rm --entrypoint tesseract $(IMAGE) --version
	docker run --rm --entrypoint pdftotext $(IMAGE) -v

push-image:
	@test -n "$(ECR_REPOSITORY_URL)" || (echo "ECR_REPOSITORY_URL is required" >&2; exit 1)
	aws ecr get-login-password --region "$(ECR_REGION)" | docker login --username AWS --password-stdin "$(ECR_REGISTRY)"
	docker buildx build --platform "$(DOCKER_PLATFORM)" --tag "$(ECR_IMAGE)" --push .
