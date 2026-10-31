#ifndef BOOTCFG_BUILD_H
#define BOOTCFG_BUILD_H

/* Overridden by the release script (scripts are in the infra repo). */
#define BOOTCFG_BUILD_TAG "dev"

const char *bootcfg_build_tag(void);

#endif
