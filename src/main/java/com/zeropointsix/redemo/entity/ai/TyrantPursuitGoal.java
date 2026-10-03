package com.zeropointsix.redemo.entity.ai;

import com.zeropointsix.redemo.entity.EncounterMob;
import java.util.EnumSet;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.ai.goal.Goal;

public final class TyrantPursuitGoal extends Goal {
    private final EncounterMob mob;

    public TyrantPursuitGoal(EncounterMob mob) {
        this.mob = mob;
        setFlags(EnumSet.of(Flag.MOVE, Flag.LOOK));
    }

    @Override
    public boolean canUse() { return EncounterMob.validTarget(mob.getTarget()) && !mob.attacking(); }

    @Override
    public void tick() {
        LivingEntity target = mob.getTarget();
        if (target == null) return;
        mob.getLookControl().setLookAt(target, 20, 20);
        if (mob.tickCount % 10 == 0) mob.getNavigation().moveTo(target, 1.0);
    }

    @Override
    public void stop() { mob.getNavigation().stop(); }
}
