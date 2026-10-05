package com.zeropointsix.redemo.entity.ai;

import com.zeropointsix.redemo.entity.EncounterMob;
import com.zeropointsix.redemo.entity.LickerEntity;
import java.util.EnumSet;
import net.minecraft.world.entity.ai.goal.Goal;
import net.minecraft.world.phys.Vec3;

public final class SoundInvestigateGoal extends Goal {
    private final LickerEntity licker;

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
    public void tick() {
        Vec3 point = EncounterMob.validTarget(licker.getTarget())
                ? licker.getTarget().position()
                : licker.investigationPoint();
        if (point == null) return;
        licker.getLookControl().setLookAt(point.x, point.y + 0.5, point.z, 25, 25);
        if (licker.tickCount % 5 == 0) licker.getNavigation().moveTo(point.x, point.y, point.z, licker.getTarget() == null ? 0.8 : 1.2);
    }

    @Override
    public void stop() { licker.getNavigation().stop(); }
}
