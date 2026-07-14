/* la_jig8 -- capture/stream application (WO-127 deliverable 2).
 *
 * The jig's reason to exist: sample 8 tapped channels off a target
 * board's debug-profile tap header and stream them to a host.
 *
 * AD-22 posture: this is APPLICATION source. The WO-37 realizer
 * generates the BSP/contract layer (pin config, clocks, linker); it
 * does NOT synthesize application logic, and nothing in the toolchain
 * invokes a compiler. This tree therefore ships as SOURCE with an
 * honest `elf: null` + elf_absent_reason -- never a fabricated image.
 * Link it against the shipped BSP with the RP2040 SDK to get a device
 * image, then pin the bytes via FirmwareArtifact.elf_content_hash.
 *
 * Capture path (why PIO, not a GPIO polling loop): the RP2040's PIO
 * state machine shifts all 8 channels in on one clock edge and pushes
 * to a DMA FIFO with no CPU involvement, so the sample interval is
 * jitter-free. A GPIO read loop cannot hold a stable rate under USB
 * interrupt load -- and a logic analyzer whose sample clock wanders is
 * worse than useless, because it lies quietly.
 */

#include <stdint.h>
#include <string.h>
#include "regolith_bsp.h"
#include "generated/debug_taps.h"
#include "la_jig8.h"

/* One sample = one byte: channel N -> bit N. This is the SAME channel
 * numbering the tap-header record publishes (tap_header_2x08_254:
 * channel N on odd pin 2N+1). The jig never renumbers channels -- the
 * pinout has exactly one home, and this is the consumer side of it. */
static uint8_t  g_ring[LA_JIG8_RING_BYTES];
static volatile uint32_t g_head;
static la_jig8_config_t  g_cfg;

void la_jig8_config_init(la_jig8_config_t *cfg)
{
    cfg->channel_mask   = 0xFFu;              /* all 8 channels armed */
    cfg->sample_hz      = LA_JIG8_DEFAULT_HZ; /* 25 MS/s burst, see below */
    cfg->trigger_mask   = 0x00u;              /* free-run until told otherwise */
    cfg->trigger_value  = 0x00u;
    cfg->post_trigger   = LA_JIG8_RING_BYTES / 2u;
}

/* Channel config over serial. The host sends a fixed 8-byte frame; we
 * refuse anything we do not fully understand rather than guessing at a
 * partial config -- a silently-misconfigured analyzer produces
 * confident wrong traces, the worst failure mode this jig has. */
int la_jig8_config_apply(const uint8_t *frame, uint32_t len)
{
    if (len != LA_JIG8_CFG_FRAME_BYTES) {
        return LA_JIG8_ERR_FRAME_LEN;
    }
    if (frame[0] != LA_JIG8_CFG_MAGIC) {
        return LA_JIG8_ERR_BAD_MAGIC;
    }
    if (frame[1] == 0x00u) {
        return LA_JIG8_ERR_NO_CHANNELS;   /* an empty mask captures nothing */
    }

    g_cfg.channel_mask  = frame[1];
    g_cfg.sample_hz     = ((uint32_t)frame[2] << 16)
                        | ((uint32_t)frame[3] << 8)
                        |  (uint32_t)frame[4];
    g_cfg.sample_hz    *= 1000u;          /* host sends kHz; we hold Hz */
    g_cfg.trigger_mask  = frame[5];
    g_cfg.trigger_value = frame[6] & frame[5];
    g_cfg.post_trigger  = (uint32_t)frame[7] * (LA_JIG8_RING_BYTES / 256u);

    if (g_cfg.sample_hz == 0u || g_cfg.sample_hz > LA_JIG8_MAX_HZ) {
        return LA_JIG8_ERR_RATE_RANGE;    /* refuse a rate we cannot hold */
    }
    return la_jig8_pio_reconfigure(&g_cfg);
}

/* The capture/stream loop.
 *
 * The 25 MS/s claim in the design source is a BURST-into-SRAM bound,
 * not a sustained-streaming bound, and the code says so out loud: at 8
 * channels x 25 MS/s the sample stream is 25 MB/s, well over what the
 * USB bulk endpoint drains. So we capture into the ring at full rate
 * and stream out behind it; when the host cannot keep up we report an
 * OVERRUN instead of silently dropping samples. A dropped sample that
 * nobody is told about turns a timing bug into a heisenbug. */
void la_jig8_run(void)
{
    la_jig8_config_init(&g_cfg);
    la_jig8_pio_reconfigure(&g_cfg);
    la_jig8_usb_init();

    for (;;) {
        uint8_t  cfg_frame[LA_JIG8_CFG_FRAME_BYTES];
        uint32_t got = la_jig8_usb_poll_config(cfg_frame, sizeof cfg_frame);
        if (got != 0u) {
            int rc = la_jig8_config_apply(cfg_frame, got);
            la_jig8_usb_send_status((uint8_t)rc);
        }

        uint32_t head = la_jig8_dma_head();
        uint32_t tail = g_head;

        if (la_jig8_dma_overrun()) {
            /* Tell the truth and resynchronize; never paper over it. */
            la_jig8_usb_send_status(LA_JIG8_ERR_OVERRUN);
            la_jig8_dma_clear_overrun();
            g_head = la_jig8_dma_head();
            continue;
        }

        while (tail != head) {
            uint32_t chunk = (head > tail) ? (head - tail)
                                           : (LA_JIG8_RING_BYTES - tail);
            if (chunk > LA_JIG8_USB_CHUNK) {
                chunk = LA_JIG8_USB_CHUNK;
            }
            la_jig8_usb_send(&g_ring[tail], chunk);

            /* Mirror each streamed chunk's first sample onto the trace
             * hook table, so a debug build of the JIG ITSELF can be
             * probed on the same tap channels it offers to others. In a
             * release build REGOLITH_TRACE compiles to nothing. */
            REGOLITH_TRACE(0, (unsigned long)g_ring[tail]);

            tail = (tail + chunk) % LA_JIG8_RING_BYTES;
            g_head = tail;
        }
    }
}
