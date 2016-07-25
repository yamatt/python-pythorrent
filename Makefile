.PHONY: docs 

clean:
	find . -name '*.pyc' -delete
	find . -name '*.pyo' -delete
	find . -name '*~' -delete
	
docs:
	$(MAKE) -C docs html
