/* la_jig8 application contract (WO-127 deliverable 2).
 *
 * Channel numbering is NOT defined here -- it is published once, in
 * std.elec's `tap_header_2x08_254` record, and this firmware consumes
 * that numbering (channel N -> bit N of a sample byte). Restating the
 * pinout in a header would create a second home for it and invite the
 * exact desync the single-home rule exists to prevent.
 */

#ifndef LA_JIG8_H
#define LA_JIG8_H

#include <stdint.h>

#define LA_JIG8_CHANNELS         8u
#define LA_JIG8_RING_BYTES       65536u
#define LA_JIG8_USB_CHUNK        512u
#define LA_JIG8_CFG_FRAME_BYTES  8u
#define LA_JIG8_CFG_MAGIC        0xA7u

/* 25 MS/s burst (see the design claim `sample_rate` in la_jig8.cupr:
 * 133MHz PIO / 2 cycles per sample = 66.5 MS/s theoretical, derated).
 * LA_JIG8_MAX_HZ is the refusal boundary, not an aspiration. */
#define LA_JIG8_DEFAULT_HZ       25000000u
#define LA_JIG8_MAX_HZ           25000000u

#define LA_JIG8_ERR_OK           0
#define LA_JIG8_ERR_FRAME_LEN   -1
#define LA_JIG8_ERR_BAD_MAGIC   -2
#define LA_JIG8_ERR_NO_CHANNELS -3
#define LA_JIG8_ERR_RATE_RANGE  -4
#define LA_JIG8_ERR_OVERRUN     -5

typedef struct {
    uint8_t  channel_mask;
    uint32_t sample_hz;
    uint8_t  trigger_mask;
    uint8_t  trigger_value;
    uint32_t post_trigger;
} la_jig8_config_t;

void la_jig8_config_init(la_jig8_config_t *cfg);
int  la_jig8_config_apply(const uint8_t *frame, uint32_t len);
void la_jig8_run(void);

/* BSP seam -- implemented against the WO-37-generated BSP. */
int      la_jig8_pio_reconfigure(const la_jig8_config_t *cfg);
uint32_t la_jig8_dma_head(void);
int      la_jig8_dma_overrun(void);
void     la_jig8_dma_clear_overrun(void);
void     la_jig8_usb_init(void);
void     la_jig8_usb_send(const uint8_t *buf, uint32_t len);
void     la_jig8_usb_send_status(uint8_t code);
uint32_t la_jig8_usb_poll_config(uint8_t *buf, uint32_t cap);

#endif /* LA_JIG8_H */
