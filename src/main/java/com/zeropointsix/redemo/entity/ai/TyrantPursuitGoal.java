package com.zeropointsix.redemo.entity.ai;

import com.zeropointsix.redemo.entity.EncounterMob;
import com.zeropointsix.redemo.entity.TyrantEntity;
import java.util.EnumSet;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.ai.goal.Goal;

public final class TyrantPursuitGoal extends Goal {
    private final EncounterMob mob;
    private int pathRefreshTicks;

    public TyrantPursuitGoal(EncounterMob mob) {
        this.mob = mob;
        setFlags(EnumSet.of(Flag.MOVE, Flag.LOOK));
    }

    @Override
    public boolean canUse() { return EncounterMob.validTarget(mob.getTarget()) && !mob.attacking(); }

    @Override
    public boolean requiresUpdateEveryTick() { return true; }

    @Override
    public void start() {
        pathRefreshTicks = 0;
        tick();
    }

    @Override
    public void tick() {
        LivingEntity target = mob.getTarget();
        if (target == null) return;
        mob.getLookControl().setLookAt(target, 20, 20);
        if (mob instanceof TyrantEntity tyrant && tyrant.hasBreakableAhead()) {
            // A four-block passage can need two bounded swings; hold the lane between them.
            mob.getNavigation().stop();
            mob.setDeltaMovement(0, mob.getDeltaMovement().y, 0);
            pathRefreshTicks = 0;
            return;
        }
        if (--pathRefreshTicks <= 0) {
            mob.getNavigation().moveTo(target, 1.0);
            pathRefreshTicks = 10;
        }
    }

    @Override
    public void stop() { mob.getNavigation().stop(); }
}
