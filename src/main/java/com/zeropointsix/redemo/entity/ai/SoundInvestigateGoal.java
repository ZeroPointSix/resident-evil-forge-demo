package com.zeropointsix.redemo.entity.ai;

import com.zeropointsix.redemo.config.CommonConfig;
import com.zeropointsix.redemo.entity.EncounterMob;
import com.zeropointsix.redemo.entity.LickerEntity;
import java.util.EnumSet;
import net.minecraft.world.entity.ai.goal.Goal;
import net.minecraft.world.phys.Vec3;

public final class SoundInvestigateGoal extends Goal {
    private final LickerEntity licker;
    private int repathTicks;

    public SoundInvestigateGoal(LickerEntity licker) {
        this.licker = licker;
        setFlags(EnumSet.of(Flag.MOVE, Flag.LOOK));
    }

    @Override
    public boolean canUse() {
        return !licker.attacking() && !licker.isHanging()
                && (licker.investigationPoint() != null || EncounterMob.validTarget(licker.getTarget()));
    }

    @Override
    public boolean canContinueToUse() {
        return canUse();
    }

    @Override
    public void start() {
        // Every attack stops navigation. Resume immediately, independent of entity tick parity.
        repathTicks = 0;
        tick();
    }

    @Override
    public boolean requiresUpdateEveryTick() { return true; }

    @Override
    public void tick() {
        if (!canUse()) return;
        Vec3 point = EncounterMob.validTarget(licker.getTarget())
                ? licker.getTarget().position()
                : licker.investigationPoint();
        if (point == null) return;
        licker.getLookControl().setLookAt(point.x, point.y + 0.5, point.z, 25, 25);
        if (--repathTicks <= 0) {
            repathTicks = CommonConfig.LICKER_REPATH_TICKS;
            licker.getNavigation().moveTo(point.x, point.y, point.z,
                    EncounterMob.validTarget(licker.getTarget()) ? CommonConfig.LICKER_PURSUIT_SPEED : CommonConfig.LICKER_INVESTIGATION_SPEED);
        }
    }

    @Override
    public void stop() { licker.getNavigation().stop(); }
}
