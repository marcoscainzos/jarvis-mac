from __future__ import annotations

from AppKit import (
    NSBackingStoreBuffered,
    NSColor,
    NSFloatingWindowLevel,
    NSPanel,
    NSScreen,
    NSView,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorFullScreenAuxiliary,
    NSWindowStyleMaskBorderless,
)
from Quartz import CABasicAnimation, CAShapeLayer, CGPathCreateWithEllipseInRect


class JarvisOverlay:
    """Núcleo visual flotante que no roba el foco al usuario."""

    def __init__(self) -> None:
        frame = ((24.0, 260.0), (220.0, 220.0))
        self.panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            frame, NSWindowStyleMaskBorderless, NSBackingStoreBuffered, False
        )
        self.panel.setOpaque_(False)
        self.panel.setBackgroundColor_(NSColor.clearColor())
        self.panel.setHasShadow_(False)
        self.panel.setHidesOnDeactivate_(False)
        self.panel.setIgnoresMouseEvents_(True)
        self.panel.setLevel_(NSFloatingWindowLevel)
        self.panel.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorFullScreenAuxiliary
        )

        screen = NSScreen.mainScreen().visibleFrame()
        self.panel.setFrameOrigin_((24.0, screen.origin.y + (screen.size.height - 220) / 2))

        container = NSView.alloc().initWithFrame_(((0.0, 0.0), (220.0, 220.0)))
        container.setWantsLayer_(True)
        self.panel.setContentView_(container)
        self._build_orb(container)

        self.state = "ready"
        self.show("ready")

    def _build_orb(self, container: NSView) -> None:
        colors = [
            (0.08, 0.72, 1.0, 0.10),
            (0.05, 0.84, 1.0, 0.16),
            (0.18, 0.94, 1.0, 0.25),
            (0.60, 0.98, 1.0, 0.82),
        ]
        sizes = [178.0, 136.0, 96.0, 42.0]
        self.layers: list[CAShapeLayer] = []
        for index, (size, color) in enumerate(zip(sizes, colors)):
            layer = CAShapeLayer.layer()
            layer.setFrame_(container.bounds())
            origin = ((220.0 - size) / 2, 21.0 + (178.0 - size) / 2)
            layer.setPath_(CGPathCreateWithEllipseInRect((origin, (size, size)), None))
            layer.setFillColor_(
                NSColor.colorWithCalibratedRed_green_blue_alpha_(*color).CGColor()
            )
            if index < 3:
                layer.setStrokeColor_(
                    NSColor.colorWithCalibratedRed_green_blue_alpha_(
                        0.15, 0.88, 1.0, 0.45 - index * 0.08
                    ).CGColor()
                )
                layer.setLineWidth_(1.2)
            container.layer().addSublayer_(layer)
            self.layers.append(layer)

    def _animate(self, state: str) -> None:
        timings = {
            "listening": (0.72, 0.86, 1.12),
            "processing": (1.65, 0.94, 1.04),
            "speaking": (0.34, 0.82, 1.16),
            "error": (0.22, 0.90, 1.10),
        }
        duration, minimum, maximum = timings.get(state, timings["listening"])
        for index, layer in enumerate(self.layers):
            layer.removeAllAnimations()
            if state == "error":
                layer.setFillColor_(
                    NSColor.colorWithCalibratedRed_green_blue_alpha_(
                        1.0, 0.42, 0.06, 0.12 + index * 0.13
                    ).CGColor()
                )
            else:
                alpha = (0.10, 0.16, 0.25, 0.82)[index]
                layer.setFillColor_(
                    NSColor.colorWithCalibratedRed_green_blue_alpha_(
                        0.08 + index * 0.12, 0.72 + index * 0.07, 1.0, alpha
                    ).CGColor()
                )
            pulse = CABasicAnimation.animationWithKeyPath_("transform.scale")
            pulse.setFromValue_(minimum + index * 0.015)
            pulse.setToValue_(maximum + index * 0.012)
            pulse.setDuration_(duration + index * (0.08 if state != "speaking" else 0.04))
            pulse.setAutoreverses_(True)
            pulse.setRepeatCount_(float("inf"))
            layer.addAnimation_forKey_(pulse, f"state-pulse-{index}")

            glow = CABasicAnimation.animationWithKeyPath_("opacity")
            glow.setFromValue_(0.30 if state == "processing" else 0.48)
            glow.setToValue_(1.0)
            glow.setDuration_(duration * (0.72 + index * 0.08))
            glow.setAutoreverses_(True)
            glow.setRepeatCount_(float("inf"))
            layer.addAnimation_forKey_(glow, f"state-glow-{index}")

    def show(self, state: str) -> None:
        if state != self.state or state == "ready":
            self._animate(state)
            self.state = state
        self.panel.setAlphaValue_(1.0)
        self.panel.orderFrontRegardless()

    def hide(self) -> None:
        self.panel.orderOut_(None)
