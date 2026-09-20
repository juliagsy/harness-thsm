.PHONY: pdf tex figures check clean

## regenerate the LaTeX sections from the markdown draft (the source of truth)
tex:
	python3 scripts/md2tex.py

## regenerate the figures from the experiment directories
figures:
	cd .. && uv run python -c "from decaymem.report.paperfigs import make_all; make_all(out='paper/figures')"

pdf:
	mkdir -p build && tectonic --keep-intermediates --keep-logs --outdir build main.tex

## a copy with a readable filename, for circulating a draft
review: pdf
	cp build/main.pdf decay-without-creep-draft.pdf
	@echo "paper/decay-without-creep-draft.pdf"

all: tex figures pdf

check: pdf
	@python3 scripts/check.py build/main.log

clean:
	rm -rf build

## arXiv wants a self-contained tarball including main.bbl (it does not rerun bibtex)
arxiv: tex figures
	rm -rf build dist && mkdir -p build dist
	tectonic --keep-intermediates --keep-logs --outdir build main.tex
	python3 scripts/check.py
	cp build/main.bbl .
	tar czf dist/arxiv-submission.tar.gz main.tex main.bbl sections figures
	rm -f main.bbl
	@echo "dist/arxiv-submission.tar.gz ready — primary cs.AI, cross-list cs.CR"
