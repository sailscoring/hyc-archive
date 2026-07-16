# Capture automation for the HYC results-site backup, ported from
# github.com/markmc/reshyc (which pre-dates Sail Scoring). Three captures,
# each landing under sources/reshyc/:
#
#   backup            mirror the results.hyc.ie FTP site (the published
#                     Sailwave HTML) into sources/reshyc/results.hyc.ie/
#   admin-backup      dump the hyc.ie admin results DB — the mapping of
#                     (year, open/club, event, class) to an FTP path —
#                     into sources/reshyc/admin/<year>_{open,club}.csv
#   summaries-backup  download the yearly prize-winner summary PDFs
#                     (1996–) into sources/reshyc/summaries/
#
# Credentials come from the environment; see .ftp_credentials.example and
# .admin_credentials.example. CI runs these via .github/workflows/backup-*.yml.

CAPTURE_DIR := sources/reshyc

require_ftp_credentials:
ifndef FTP_SERVER
	$(error FTP_SERVER is not defined)
endif
ifndef FTP_USER
	$(error FTP_USER is not defined)
endif
ifndef FTP_PASSWORD
	$(error FTP_PASSWORD is not defined)
endif

backup: require_ftp_credentials
	@cd $(CAPTURE_DIR) && wget -m ftp://$(FTP_USER):$(FTP_PASSWORD)@$(FTP_SERVER)/$(FTP_DIR)
	find $(CAPTURE_DIR)/results.hyc.ie/ -name .listing -delete

require_admin_credentials:
ifndef ADMIN_USERNAME
	$(error ADMIN_USERNAME is not defined)
endif
ifndef ADMIN_PASSWORD
	$(error ADMIN_PASSWORD is not defined)
endif

ADMIN_YEARS := 2026 2025 2024 2023 2022 2021 2020 2019 2018 2017 2016 2015 2014 2013
ADMIN_FILES := $(foreach year,$(ADMIN_YEARS),$(CAPTURE_DIR)/admin/$(year)_open.csv $(CAPTURE_DIR)/admin/$(year)_club.csv)

$(CAPTURE_DIR)/admin/%.csv:
	@year=$$(echo $@ | sed 's|.*/\(.*\)_.*.csv|\1|'); \
	event_type=$$(echo $@ | sed 's|.*/.*_\(.*\).csv|\1|'); \
	echo "Generating $@"; \
	./scripts/admin/get-results --csv $$year $$event_type > $@

admin-backup: require_admin_credentials $(ADMIN_FILES)

admin-backup-clean:
	rm -f $(ADMIN_FILES)

summaries-backup: require_admin_credentials
	./scripts/admin/download-results-summaries $(CAPTURE_DIR)/summaries/
