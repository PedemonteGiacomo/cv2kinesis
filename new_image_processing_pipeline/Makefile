.PHONY: build-base
build-base:
docker build -t mip-base -f containers/base/Dockerfile .

.PHONY: build-algos
build-algos: build-base
for a in processing_1 processing_6 ; do \
docker build -t mip-$$a -f containers/$$a/Dockerfile . ; \
done

.PHONY: test
test:
pytest -q tests
