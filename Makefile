ANKI_PYTHON ?= /Applications/Anki.app/Contents/Frameworks/Python.framework/Versions/3.13/bin/python3
NAME := anki_field_exporter
DIST := dist
SHIPPED := __init__.py exporter.py settings.py manifest.json config.json config.md

.PHONY: test unit integration install clean package release bump

test: unit integration

unit:
	python3 tests/test_exporter.py

integration:
	$(ANKI_PYTHON) tests/test_with_anki.py
	$(ANKI_PYTHON) tests/test_gui_wiring.py
	$(ANKI_PYTHON) tests/test_settings_dialog.py

install:
	./install.sh

bump:
	python3 -c "import json,time,pathlib; p=pathlib.Path('manifest.json'); m=json.loads(p.read_text()); m['mod']=int(time.time()); p.write_text(json.dumps(m, indent=2)+'\n'); print('mod ->', m['mod'])"

package:
	mkdir -p $(DIST)
	rm -f $(DIST)/$(NAME).ankiaddon
	zip -q -X $(DIST)/$(NAME).ankiaddon $(SHIPPED)
	@echo "built $(DIST)/$(NAME).ankiaddon"
	@unzip -l $(DIST)/$(NAME).ankiaddon | tail -n +2

release: bump package

clean:
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
	rm -rf $(DIST)
