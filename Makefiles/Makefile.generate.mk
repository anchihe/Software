
generate:
	@echo "$(sep)Automated files generation"
	@echo
	@echo 'Generation of documentation'
	@echo
	@echo '    generate-all              Generates everything'
	@echo '    generate-help             Generates help'
	@echo '    generate-easy_node        Generates the easy node documentation'
	@echo '    generate-easy_node-clean  Cleans the generated files'


generate-all: \
	generate-help\
	generate-easy_node

out_help=Makefiles/help.autogenerated.md

generate-help:
	echo '## Makefile help {#makefiles-autogenerated}' > $(out_help)
	$(MAKE) -s all >> $(out_help)


generate-easy_node:
	rosrun easy_node generate_docs

generate-easy_node-clean:
	find . -name '*autogenerated.md' -delete
