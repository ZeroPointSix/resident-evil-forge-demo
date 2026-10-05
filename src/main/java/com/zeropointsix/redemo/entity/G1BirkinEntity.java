package com.zeropointsix.redemo.entity;

import com.zeropointsix.redemo.config.CommonConfig;
import com.zeropointsix.redemo.entity.ai.TyrantPursuitGoal;
import com.zeropointsix.redemo.registry.ModSounds;
import java.util.UUID;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.syncher.EntityDataAccessor;
import net.minecraft.network.syncher.EntityDataSerializers;
import net.minecraft.network.syncher.SynchedEntityData;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.util.Mth;
import net.minecraft.world.BossEvent;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.effect.MobEffectInstance;
import net.minecraft.world.effect.MobEffects;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityDimensions;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.Pose;
import net.minecraft.world.entity.ai.attributes.AttributeSupplier;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.ai.goal.FloatGoal;
import net.minecraft.world.entity.ai.goal.WaterAvoidingRandomStrollGoal;
import net.minecraft.world.entity.ai.goal.target.HurtByTargetGoal;
import net.minecraft.world.entity.ai.goal.target.NearestAttackableTargetGoal;
import net.minecraft.world.entity.monster.Monster;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.entity.projectile.Projectile;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.entity.PartEntity;

public final class G1BirkinEntity extends EncounterMob {
    public static final int SLAM = 1, SWEEP = 2, GRAB = 3, RAGE = 4;
    // Center of the visible eye cubes in the stable exposure pose, in model pixels.
    // GeckoLib reverses model Z when the entity faces Minecraft's positive Z.
    public static final Vec3 EYE_LOCAL_CENTER = new Vec3(9.600001 / 16, 38.080002 / 16, 9.800001 / 16);
    public static final String[] EXPOSURE_BONES = { "root", "pelvis", "torso", "chest", "right_shoulder", "eye_open" };
    private static final EntityDataAccessor<Boolean> EYE_OPEN = SynchedEntityData.defineId(G1BirkinEntity.class, EntityDataSerializers.BOOLEAN);
    private static final EntityDataAccessor<Boolean> BERSERK = SynchedEntityData.defineId(G1BirkinEntity.class, EntityDataSerializers.BOOLEAN);
    private final EyePart eye;
    private final PartEntity<?>[] parts;
    private int weakTicks;
    private int skillSequence;
    private UUID grabbed;
    private boolean resolvingWeakHit;

    public G1BirkinEntity(EntityType<? extends Monster> type, Level level) {
        super(type, level);
        eye = new EyePart(this);
        parts = new PartEntity<?>[] { eye };
        setId(ENTITY_COUNTER.getAndAdd(2) + 1);
        enableBossBar(BossEvent.BossBarColor.YELLOW);
        setMaxUpStep(1.0F);
    }

    public static AttributeSupplier.Builder attributes() {
        return Monster.createMonsterAttributes().add(Attributes.MAX_HEALTH, CommonConfig.BIRKIN_HEALTH)
                .add(Attributes.ARMOR, 8).add(Attributes.MOVEMENT_SPEED, 0.24)
                .add(Attributes.ATTACK_DAMAGE, 14).add(Attributes.FOLLOW_RANGE, 40)
                .add(Attributes.KNOCKBACK_RESISTANCE, 0.7);
    }

    @Override
    protected void defineSynchedData() {
        super.defineSynchedData();
        entityData.define(EYE_OPEN, false);
        entityData.define(BERSERK, false);
    }

    @Override
    protected void registerGoals() {
        goalSelector.addGoal(0, new FloatGoal(this));
        goalSelector.addGoal(1, new TyrantPursuitGoal(this));
        goalSelector.addGoal(6, new WaterAvoidingRandomStrollGoal(this, 0.6));
        targetSelector.addGoal(1, new HurtByTargetGoal(this));
        targetSelector.addGoal(2, new NearestAttackableTargetGoal<>(this, Player.class, true));
    }

    @Override
    public void setId(int id) {
        super.setId(id);
        if (eye != null) eye.setId(id + 1);
    }

    @Override
    public boolean isMultipartEntity() { return true; }

    @Override
    public PartEntity<?>[] getParts() { return parts; }

    public EyePart eyePart() { return eye; }
    public boolean isEyeOpen() { return entityData.get(EYE_OPEN); }
    public boolean isBerserk() { return entityData.get(BERSERK); }

    public Vec3 eyeCenter() {
        return EYE_LOCAL_CENTER.yRot(-yBodyRot * Mth.DEG_TO_RAD).add(position());
    }

    public void openWeakPoint(int ticks) {
        if (level().isClientSide || !isAlive()) return;
        if (!isEyeOpen()) playSound(ModSounds.EYE_OPEN.get(), 1.2F, 1.3F);
        weakTicks = Math.max(weakTicks, ticks);
        entityData.set(EYE_OPEN, true);
    }

    public void updatePhase() {
        if (level().isClientSide || !isAlive() || isBerserk() || getHealth() > getMaxHealth() * 0.30F) return;
        entityData.set(BERSERK, true);
        openWeakPoint(100);
        if (!attacking()) startAttack(RAGE, 40, 15);
        playSound(ModSounds.RAGE.get(), 1.7F, 1.1F);
    }

    @Override
    public void tick() {
        super.tick();
        Vec3 location = eyeCenter();
        eye.setPos(location.x, location.y - eye.getBbHeight() * 0.5, location.z);
        if (level().isClientSide || !isAlive()) return;
        updatePhase();
        if (weakTicks > 0) weakTicks--;
        entityData.set(EYE_OPEN, weakTicks > 0);
        if (isEyeOpen() && tickCount % 6 == 0 && level() instanceof ServerLevel server) {
            server.sendParticles(ParticleTypes.CRIT, location.x, location.y, location.z, 2, 0.12, 0.12, 0.12, 0);
        }
        if (!validTarget(getTarget())) setTarget(null);
        if (!isNoAi() && !attacking() && cooldown == 0 && getTarget() != null && distanceTo(getTarget()) <= 3.4 && hasLineOfSight(getTarget())) {
            int skill = switch (skillSequence++ % 3) { case 1 -> SWEEP; case 2 -> GRAB; default -> SLAM; };
            startAttack(skill, skill == SLAM ? 36 : 40, isBerserk() ? 12 : 35);
        }
    }

    @Override
    protected void attackFrame(int attack, int tick) {
        if (attack == SLAM && tick == 18) {
            strike(3.3, 140, 14, 0.7);
            openWeakPoint(isBerserk() ? 100 : 60);
            if (level() instanceof ServerLevel server) server.sendParticles(ParticleTypes.POOF, getX() + forward().x * 2, getY() + 0.1, getZ() + forward().z * 2, 20, 1.2, 0.1, 1.2, 0.05);
        }
        if (attack == SWEEP && tick == 20) {
            strike(3.6, 160, 18, 1.0);
            openWeakPoint(isBerserk() ? 110 : 65);
        }
        if (attack == GRAB && tick == 15) {
            strike(2.8, 75, 6, 0);
            LivingEntity target = getTarget();
            if (target != null && attackHits.contains(target.getUUID())) {
                grabbed = target.getUUID();
                target.addEffect(new MobEffectInstance(MobEffects.MOVEMENT_SLOWDOWN, 18, 5, false, true));
            }
        }
        if (attack == GRAB && tick == 30) {
            if (grabbed != null && level() instanceof ServerLevel server && server.getEntity(grabbed) instanceof LivingEntity victim && validTarget(victim) && distanceTo(victim) <= 4 && clearAttackLine(victim)) {
                victim.hurt(damageSources().mobAttack(this), 8 * CommonConfig.DAMAGE_SCALE.get().floatValue());
                Vec3 direction = forward();
                victim.push(direction.x * 1.1, 0.65, direction.z * 1.1);
                victim.hurtMarked = true;
            }
            grabbed = null;
            openWeakPoint(isBerserk() ? 110 : 65);
        }
    }

    @Override
    protected void onAttackFinished() { grabbed = null; }

    private boolean attackIntersectsEye(DamageSource source) {
        if (!isEyeOpen()) return false;
        if (source.getDirectEntity() instanceof Projectile p) {
            Vec3 motion = p.getDeltaMovement();
            return eyeIsFirstIntersection(p.position(), p.position().add(motion), 0.12);
        }
        if (source.getDirectEntity() instanceof LivingEntity attacker && attacker.distanceTo(this) < 6) {
            Vec3 start = attacker.getEyePosition();
            return eyeIsFirstIntersection(start, start.add(attacker.getViewVector(1).scale(6)), 0);
        }
        return false;
    }

    private boolean eyeIsFirstIntersection(Vec3 start, Vec3 end, double padding) {
        AABB eyeBox = eye.getBoundingBox().inflate(padding);
        AABB bodyBox = getBoundingBox().inflate(padding);
        var eyeHit = eyeBox.contains(start) ? java.util.Optional.of(start) : eyeBox.clip(start, end);
        if (eyeHit.isEmpty()) return false;
        var bodyHit = bodyBox.contains(start) ? java.util.Optional.of(start) : bodyBox.clip(start, end);
        // A ray reaching the eye only after entering the body is a normal body hit.
        return bodyHit.isEmpty() || start.distanceToSqr(eyeHit.get()) <= start.distanceToSqr(bodyHit.get()) + 1.0E-7;
    }

    @Override
    public boolean hurt(DamageSource source, float amount) { return takeHit(source, amount, attackIntersectsEye(source)); }

    private boolean takeHit(DamageSource source, float amount, boolean eyeHit) {
        boolean bonus = eyeHit && isEyeOpen();
        boolean hit;
        resolvingWeakHit = bonus;
        try {
            hit = super.hurt(source, amount);
        } finally {
            resolvingWeakHit = false;
        }
        if (hit && bonus && !level().isClientSide) {
            playSound(ModSounds.EYE_OPEN.get(), 1.4F, 1.8F);
            if (level() instanceof ServerLevel server) server.sendParticles(ParticleTypes.DAMAGE_INDICATOR, eye.getX(), eye.getY() + 0.35, eye.getZ(), 8, 0.2, 0.2, 0.2, 0.1);
        }
        return hit;
    }

    @Override
    protected float getDamageAfterMagicAbsorb(DamageSource source, float amount) {
        float reduced = super.getDamageAfterMagicAbsorb(source, amount);
        return resolvingWeakHit ? reduced * (float) CommonConfig.EYE_MULTIPLIER : reduced;
    }

    @Override
    protected String attackAnimation(int attack) {
        return switch (attack) { case SWEEP -> "sweep"; case GRAB -> "grab"; case RAGE -> "rage"; default -> "slam"; };
    }

    @Override
    public String assetId() { return "g1_birkin"; }

    @Override
    public int deathDurationTicks() { return 64; }

    @Override
    public void die(DamageSource source) {
        super.die(source);
        weakTicks = 0;
        grabbed = null;
        entityData.set(EYE_OPEN, false);
    }

    @Override
    public void readAdditionalSaveData(CompoundTag tag) {
        super.readAdditionalSaveData(tag);
        weakTicks = 0;
        grabbed = null;
        entityData.set(EYE_OPEN, false);
        entityData.set(BERSERK, false);
    }

    public static final class EyePart extends PartEntity<G1BirkinEntity> {
        public EyePart(G1BirkinEntity parent) {
            super(parent);
            refreshDimensions();
        }

        @Override
        public EntityDimensions getDimensions(Pose pose) { return EntityDimensions.fixed(0.7F, 0.7F); }

        @Override
        protected void defineSynchedData() { }

        @Override
        protected void readAdditionalSaveData(CompoundTag tag) { }

        @Override
        protected void addAdditionalSaveData(CompoundTag tag) { }

        @Override
        public boolean isPickable() { return getParent().isAlive(); }

        @Override
        public boolean is(Entity other) { return this == other || getParent() == other; }

        @Override
        public boolean hurt(DamageSource source, float amount) { return !isInvulnerableTo(source) && getParent().takeHit(source, amount, true); }
    }
}
