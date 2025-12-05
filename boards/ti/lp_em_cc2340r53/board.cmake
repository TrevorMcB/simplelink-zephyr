# Copyright (c) 2024 Texas Instruments Incorporated
# Copyright (c) 2024 BayLibre, SAS
#
# SPDX-License-Identifier: Apache-2.0
#board_set_flasher(openocd)
board_runner_args(jlink "--device=CC2340R53")
board_runner_args(openocd "--config=${ZEPHYR_BASE}/openocd_20250414/share/openocd/scripts/board/ti_lp_em_cc2340r53.cfg")
board_runner_args(openocd "--openocd=${ZEPHYR_BASE}/openocd_20250414/bin/openocd.exe")

include(${ZEPHYR_BASE}/boards/common/jlink.board.cmake)
board_set_flasher(openocd)
include(${ZEPHYR_BASE}/boards/common/openocd.board.cmake)
