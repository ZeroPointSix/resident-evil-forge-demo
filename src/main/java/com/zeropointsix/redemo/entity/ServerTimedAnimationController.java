package com.zeropointsix.redemo.entity;

import com.mojang.logging.LogUtils;
import java.util.List;
import java.util.Map;
import software.bernie.geckolib.core.animatable.model.CoreGeoBone;
import software.bernie.geckolib.core.animatable.model.CoreGeoModel;
import software.bernie.geckolib.core.animation.AnimationController;
import software.bernie.geckolib.core.animation.AnimationState;
import software.bernie.geckolib.core.animation.EasingType;
import software.bernie.geckolib.core.keyframe.Keyframe;
import software.bernie.geckolib.core.state.BoneSnapshot;

/** Single-stage attacks use replicated server progress, including their first visible frame. */
final class ServerTimedAnimationController extends AnimationController<EncounterMob> {
    private int sequence = Integer.MIN_VALUE;
    private boolean attackFrame;
    private double partialTick;
    private double lastSeek = Double.NEGATIVE_INFINITY;
    private int lastLoggedTick = -1;

    ServerTimedAnimationController(EncounterMob mob, AnimationStateHandler<EncounterMob> handler) {
        super(mob, "action", 0, handler);
    }

    @Override
    public void process(CoreGeoModel<EncounterMob> model, AnimationState<EncounterMob> state,
                        Map<String, CoreGeoBone> bones, Map<String, BoneSnapshot> snapshots,
                        double seekTime, boolean crashWhenCantFindBone) {
        attackFrame = animatable.isAlive() && animatable.attacking();
        partialTick = state.getPartialTick();
        boolean first = attackFrame && sequence != animatable.attackSequence();
        boolean resumed = attackFrame && Double.isFinite(lastSeek) && seekTime - lastSeek > 3;
        if (first) {
            sequence = animatable.attackSequence();
            forceAnimationReset();
        }
        super.process(model, state, bones, snapshots, seekTime, crashWhenCantFindBone);
        // GeckoLib 4.4.9 must initialize its animation queue at tick zero. Complete
        // that zero-length transition before the processor consumes this frame.
        if (attackFrame && getAnimationState() == State.TRANSITIONING && currentAnimation != null) {
            super.process(model, state, bones, snapshots, seekTime, crashWhenCantFindBone);
        }
        if (EncounterMob.ANIMATION_TRACE && attackFrame
                && (first || resumed || lastLoggedTick != animatable.attackTick())) {
            traceSample(first, resumed);
            lastLoggedTick = animatable.attackTick();
        }
        lastSeek = seekTime;
    }

    @Override
    protected double adjustTick(double tick) {
        double localTick = super.adjustTick(tick);
        if (!attackFrame || getAnimationState() != State.RUNNING || currentAnimation == null) return localTick;
        double progress = (animatable.attackTick() + partialTick) * getAnimationSpeed();
        // Integer server durations can round beyond the final animation keyframe.
        return Math.min(progress, Math.max(0, Math.nextDown(currentAnimation.animation().length())));
    }

    private void traceSample(boolean first, boolean resumed) {
        if (currentAnimation == null) return;
        for (var animation : currentAnimation.animation().boneAnimations()) {
            var queue = getBoneAnimationQueues().get(animation.boneName());
            var point = queue == null ? null : queue.rotationXQueue().peek();
            // Only frame identity and duration are needed, not GeckoLib's math value type.
            List<?> frames = animation.rotationKeyFrames().xKeyframes();
            if (point == null || point.keyFrame() == null || frames.size() < 2) continue;
            if (Math.abs(point.animationStartValue() - point.animationEndValue()) < 1e-7) continue;
            double prefix = 0;
            for (int index = 0; index < frames.size(); index++) {
                Keyframe<?> frame = (Keyframe<?>) frames.get(index);
                if (frame == point.keyFrame()) {
                    // These are the actual points queued by GeckoLib's private sampler,
                    // not a second copy of the requested/expected progress.
                    LogUtils.getLogger().info(
                            "RE_DEMO_SYNC_CLIENT uuid={} asset={} seq={} attack={} tick={} partial={} speed={} clip={} length={} bone={} prefix={} point={} segment={} last={} value={} first={} resumed={} state={}",
                            animatable.getUUID(), animatable.assetId(), sequence, animatable.attack(),
                            animatable.attackTick(), partialTick, getAnimationSpeed(), currentAnimation.animation().name(),
                            currentAnimation.animation().length(), animation.boneName(), prefix, point.currentTick(),
                            point.transitionLength(), index == frames.size() - 1, EasingType.lerpWithOverride(point, null),
                            first, resumed, getAnimationState());
                    return;
                }
                prefix += frame.length();
            }
        }
    }
}
