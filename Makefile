IMAGE ?= single-pass-parsing-model-ranker:local

.PHONY: build-image smoke-image

build-image:
	docker build --tag $(IMAGE) .

smoke-image: build-image
	docker run --rm $(IMAGE) --help
	docker run --rm --entrypoint tesseract $(IMAGE) --version
	docker run --rm --entrypoint pdftotext $(IMAGE) -v
