from __future__ import annotations

from AppKit import (
    NSBackingStoreBuffered,
    NSColor,
    NSFloatingWindowLevel,
    NSFont,
    NSPanel,
    NSScreen,
    NSTextAlignmentCenter,
    NSTextField,
    NSView,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorFullScreenAuxiliary,
    NSWindowStyleMaskBorderless,
)
from Quartz import CABasicAnimation, CAShapeLayer, CGPathCreateWithEllipseInRect


class JarvisOverlay:
    """Núcleo visual flotante que no roba el foco al usuario."""

    def __init__(self) -> None:
        frame = ((24.0, 260.0), (220.0, 230.0))
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
        self.panel.setFrameOrigin_((24.0, screen.origin.y + (screen.size.height - 230) / 2))

        container = NSView.alloc().initWithFrame_(((0.0, 0.0), (220.0, 230.0)))
        container.setWantsLayer_(True)
        self.panel.setContentView_(container)
        self._build_orb(container)

        self.label = NSTextField.labelWithString_("ESCUCHANDO")
        self.label.setFrame_(((10.0, 12.0), (200.0, 28.0)))
        self.label.setAlignment_(NSTextAlignmentCenter)
        self.label.setFont_(NSFont.monospacedSystemFontOfSize_weight_(12.0, 0.55))
        self.label.setTextColor_(
            NSColor.colorWithCalibratedRed_green_blue_alpha_(0.35, 0.92, 1.0, 0.95)
        )
        container.addSubview_(self.label)
        self.show("ready")

    def _build_orb(self, container: NSView) -> None:
        colors = [
            (0.08, 0.72, 1.0, 0.10),
            (0.05, 0.84, 1.0, 0.16),
            (0.18, 0.94, 1.0, 0.25),
            (0.60, 0.98, 1.0, 0.82),
        ]
        sizes = [178.0, 136.0, 96.0, 42.0]
        for index, (size, color) in enumerate(zip(sizes, colors)):
            layer = CAShapeLayer.layer()
            layer.setFrame_(container.bounds())
            origin = ((220.0 - size) / 2, 42.0 + (178.0 - size) / 2)
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

            pulse = CABasicAnimation.animationWithKeyPath_("transform.scale")
            pulse.setFromValue_(0.88 + index * 0.02)
            pulse.setToValue_(1.08 + index * 0.03)
            pulse.setDuration_(1.25 + index * 0.22)
            pulse.setAutoreverses_(True)
            pulse.setRepeatCount_(float("inf"))
            layer.addAnimation_forKey_(pulse, f"jarvis-pulse-{index}")

            glow = CABasicAnimation.animationWithKeyPath_("opacity")
            glow.setFromValue_(0.45)
            glow.setToValue_(1.0)
            glow.setDuration_(0.8 + index * 0.18)
            glow.setAutoreverses_(True)
            glow.setRepeatCount_(float("inf"))
            layer.addAnimation_forKey_(glow, f"jarvis-glow-{index}")

    def show(self, state: str) -> None:
        labels = {
            "ready": "JARVIS",
            "listening": "ESCUCHANDO",
            "processing": "PROCESANDO",
            "speaking": "HABLANDO",
        }
        self.label.setStringValue_(labels.get(state, "JARVIS"))
        self.panel.setAlphaValue_(0.42 if state == "ready" else 1.0)
        self.panel.orderFrontRegardless()

    def hide(self) -> None:
        self.panel.orderOut_(None)
