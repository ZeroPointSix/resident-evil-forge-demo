package com.zeropointsix.redemo.entity;

import com.zeropointsix.redemo.config.CommonConfig;
import com.zeropointsix.redemo.entity.ai.SoundInvestigateGoal;
import com.zeropointsix.redemo.registry.ModSounds;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.network.syncher.EntityDataAccessor;
import net.minecraft.network.syncher.EntityDataSerializers;
import net.minecraft.network.syncher.SynchedEntityData;
import net.minecraft.sounds.SoundEvent;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.ai.attributes.AttributeSupplier;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.ai.goal.FloatGoal;
import net.minecraft.world.entity.ai.goal.WaterAvoidingRandomStrollGoal;
import net.minecraft.world.entity.ai.navigation.PathNavigation;
import net.minecraft.world.entity.ai.navigation.WallClimberNavigation;
import net.minecraft.world.entity.monster.Monster;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.Vec3;

public final class LickerEntity extends EncounterMob {
    public static final int CLAW = 1, LEAP = 2, TONGUE = 3, AMBUSH = 4;
    private static final EntityDataAccessor<Boolean> CLIMBING = SynchedEntityData.defineId(LickerEntity.class, EntityDataSerializers.BOOLEAN);
    private static final EntityDataAccessor<Boolean> HANGING = SynchedEntityData.defineId(LickerEntity.class, EntityDataSerializers.BOOLEAN);
    private Vec3 lastSound;
    private int lastSoundTick = -10000;
    private boolean combatLock;
    private int hangTicks;
    private int leapCooldown;
    private int tongueCooldown;
    private int hangCooldown;

    public LickerEntity(EntityType<? extends Monster> type, Level level) { super(type, level); }

    public static AttributeSupplier.Builder attributes() {
        return Monster.createMonsterAttributes().add(Attributes.MAX_HEALTH, CommonConfig.LICKER_HEALTH)
                .add(Attributes.ARMOR, 4).add(Attributes.MOVEMENT_SPEED, CommonConfig.LICKER_MOVE_SPEED)
                .add(Attributes.KNOCKBACK_RESISTANCE, CommonConfig.LICKER_KNOCKBACK_RESISTANCE)
                .add(Attributes.ATTACK_DAMAGE, CommonConfig.LICKER_CLAW_DAMAGE).add(Attributes.FOLLOW_RANGE, 24);
    }

    @Override
    protected void defineSynchedData() {
        super.defineSynchedData();
        entityData.define(CLIMBING, false);
        entityData.define(HANGING, false);
    }

    @Override
    protected void registerGoals() {
        goalSelector.addGoal(0, new FloatGoal(this));
        goalSelector.addGoal(1, new SoundInvestigateGoal(this));
        goalSelector.addGoal(6, new WaterAvoidingRandomStrollGoal(this, 0.65));
    }

    @Override
    protected PathNavigation createNavigation(Level level) { return new WallClimberNavigation(this, level); }

    @Override
    public boolean onClimbable() { return entityData.get(CLIMBING); }

    public boolean isHanging() { return entityData.get(HANGING); }
    public Vec3 investigationPoint() { return lastSound; }
    public boolean hasCombatLock() { return combatLock; }

    boolean inClawRange(LivingEntity target) {
        // Use the same victim radius as the contact test, avoiding an idle ring
        // around wide targets while the tongue is cooling down.
        return validTarget(target)
                && distanceTo(target) <= CommonConfig.LICKER_CLAW_RANGE + target.getBbWidth() * 0.5
                && Math.abs(target.getY() - getY()) <= CommonConfig.MELEE_MAX_Y_DIFFERENCE
                && getBoundingBox().inflate(CommonConfig.LICKER_CLAW_RANGE, CommonConfig.MELEE_VERTICAL_SEARCH,
                        CommonConfig.LICKER_CLAW_RANGE).intersects(target.getBoundingBox())
                && hasLineOfSight(target) && clearAttackLine(target);
    }

    public void hear(Vec3 position, LivingEntity source, double radius) {
        if (level().isClientSide || !isAlive() || position.distanceToSqr(position()) > radius * radius) return;
        boolean repeated = lastSound != null && tickCount - lastSoundTick < 50;
        lastSound = position;
        lastSoundTick = tickCount;
        if (repeated && validTarget(source)) setTarget(source);
    }

    @Override
    public boolean hurt(DamageSource source, float amount) {
        boolean damaged = super.hurt(source, amount);
        if (damaged && isAlive() && !level().isClientSide && source.getEntity() instanceof LivingEntity attacker && validTarget(attacker)) {
            // Hurt chase is independent of the 6s sound-memory hunt. Silent
            // NoAI dummies never emit footsteps, so routing retaliation through
            // hear() used to drop the claw target when SOUND_MEMORY_TICKS elapsed.
            combatLock = true;
            setTarget(attacker);
        }
        return damaged;
    }

    @Override
    public void die(DamageSource source) {
        lastSound = null;
        combatLock = false;
        entityData.set(CLIMBING, false);
        entityData.set(HANGING, false);
        setNoGravity(false);
        super.die(source);
    }

    @Override
    public void tick() {
        super.tick();
        if (level().isClientSide || !isAlive()) return;
        leapCooldown = Math.max(0, leapCooldown - 1);
        tongueCooldown = Math.max(0, tongueCooldown - 1);
        hangCooldown = Math.max(0, hangCooldown - 1);
        boolean melee = inClawRange(getTarget());
        // Only an unobstructed claw target is "melee". A nearby dummy
        // behind a wall still has to be climbed; colliding with that dummy in
        // the open must not spider-climb its hurtbox.
        boolean huntClimb = lastSound != null || combatLock;
        entityData.set(CLIMBING, !melee && horizontalCollision && (!onGround() || huntClimb));
        if (tickCount - lastSoundTick >= CommonConfig.SOUND_MEMORY_TICKS.get()) {
            lastSound = null;
            if (!combatLock && !melee && !attacking()) setTarget(null);
        }
        if (!validTarget(getTarget())) {
            setTarget(null);
            combatLock = false;
        }
        if (onClimbable() && huntClimb && !isHanging() && !attacking() && !melee) {
            setDeltaMovement(getDeltaMovement().x, Math.max(0.2, getDeltaMovement().y), getDeltaMovement().z);
        }
        BlockPos ceiling = BlockPos.containing(getX(), getBoundingBox().maxY + 0.15, getZ());
        boolean solidCeiling = level().getBlockState(ceiling).isFaceSturdy(level(), ceiling, Direction.DOWN);
        if (!isHanging() && !attacking() && !onGround() && solidCeiling && lastSound != null && hangCooldown == 0) {
            entityData.set(HANGING, true);
            hangTicks = 0;
            setPos(getX(), ceiling.getY() - getBbHeight(), getZ());
        }
        if (isHanging()) {
            setNoGravity(true);
            setDeltaMovement(Vec3.ZERO);
            getNavigation().stop();
            // NoAI staging (capture hang still) must not run the 50-tick auto-drop:
            // LivingEntity skips travel() while NoAI, so AMBUSH would freeze at hang Y.
            if (isNoAi()) return;
            hangTicks++;
            if (!solidCeiling || hangTicks >= 50 || getTarget() != null && hangTicks >= 20 && distanceTo(getTarget()) < 7) {
                entityData.set(HANGING, false);
                setNoGravity(false);
                hangCooldown = 160;
                if (validTarget(getTarget())) startAttack(AMBUSH, 28, 6, CommonConfig.LICKER_ATTACK_SPEED);
            }
            return;
        }
        if (isNoAi() || attacking() || cooldown > 0 || getTarget() == null) return;
        double range = distanceTo(getTarget());
        if (!hasLineOfSight(getTarget())) return;
        if (range <= CommonConfig.LICKER_TONGUE_RANGE && tongueCooldown == 0) {
            startAttack(TONGUE, 24, CommonConfig.LICKER_TONGUE_RECOVERY, CommonConfig.LICKER_ATTACK_SPEED);
            tongueCooldown = CommonConfig.LICKER_TONGUE_COOLDOWN;
            playSound(ModSounds.LICKER_TONGUE.get(), 1, 1);
        } else if (range >= 4 && range <= 7 && leapCooldown == 0 && onGround()) {
            startAttack(LEAP, 28, 6, CommonConfig.LICKER_ATTACK_SPEED);
            leapCooldown = CommonConfig.LICKER_LEAP_COOLDOWN;
            playSound(ModSounds.LICKER_HISS.get(), 1, 1.2F);
        } else if (inClawRange(getTarget())) startAttack(CLAW, 20, CommonConfig.LICKER_RECOVERY, CommonConfig.LICKER_ATTACK_SPEED);
    }

    @Override
    protected void attackFrame(int attack, int tick) {
        int hitFrame = attack == CLAW ? 9 : attack == TONGUE ? CommonConfig.LICKER_TONGUE_HIT_FRAME : attack == LEAP ? 12 : 8;
        if (tick < attackFrameAt(hitFrame)) {
            trackWindup(attack == TONGUE ? CommonConfig.LICKER_TONGUE_TRACKING : 16);
            if (attack == CLAW) advanceTowardTarget(CommonConfig.LICKER_PRESSURE_STEP, 1.6);
            else if (attack == TONGUE) advanceTowardTarget(CommonConfig.LICKER_PRESSURE_STEP, 2.8);
        }
        if (attack == CLAW && tick == attackFrameAt(9)) strike(CommonConfig.LICKER_CLAW_RANGE, 110, CommonConfig.LICKER_CLAW_DAMAGE, 0.15);
        if (attack == TONGUE && tick == attackFrameAt(CommonConfig.LICKER_TONGUE_HIT_FRAME)) {
            strike(CommonConfig.LICKER_TONGUE_RANGE, CommonConfig.LICKER_TONGUE_ARC, CommonConfig.LICKER_TONGUE_DAMAGE, 0);
            LivingEntity target = getTarget();
            if (target != null && attackHits.contains(target.getUUID())) {
                Vec3 pull = position().subtract(target.position()).normalize().scale(CommonConfig.LICKER_TONGUE_PULL);
                target.push(pull.x, 0.12, pull.z);
                target.hurtMarked = true;
            }
        }
        if ((attack == LEAP && tick == attackFrameAt(12)) || (attack == AMBUSH && tick == attackFrameAt(8))) {
            Vec3 direction = forward();
            double speed = attack == LEAP ? 0.82 : 0.65;
            setDeltaMovement(direction.x * speed, attack == LEAP ? 0.48 : -0.35, direction.z * speed);
            hasImpulse = true;
        }
        if ((attack == LEAP && tick >= attackFrameAt(13)) || (attack == AMBUSH && tick >= attackFrameAt(9))) {
            strike(1.7, 130, attack == AMBUSH ? CommonConfig.LICKER_AMBUSH_DAMAGE : CommonConfig.LICKER_LEAP_DAMAGE, 0.5);
        }
    }

    @Override
    protected String attackAnimation(int attack) {
        return switch (attack) { case LEAP -> "leap"; case TONGUE -> "tongue"; case AMBUSH -> "ambush"; default -> "claw"; };
    }

    @Override
    public String assetId() { return "licker"; }

    @Override
    public int deathDurationTicks() { return 48; }

    @Override
    protected SoundEvent getHurtSound(DamageSource source) { return ModSounds.LICKER_HURT.get(); }

    @Override
    protected SoundEvent getDeathSound() { return ModSounds.LICKER_DEATH.get(); }

    @Override
    public boolean causeFallDamage(float distance, float multiplier, DamageSource source) { return false; }
}
