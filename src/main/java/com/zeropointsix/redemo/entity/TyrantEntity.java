package com.zeropointsix.redemo.entity;

import com.zeropointsix.redemo.ResidentEvilMod;
import com.zeropointsix.redemo.config.CommonConfig;
import com.zeropointsix.redemo.entity.ai.TyrantPursuitGoal;
import com.zeropointsix.redemo.registry.ModSounds;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.Registries;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.syncher.EntityDataAccessor;
import net.minecraft.network.syncher.EntityDataSerializers;
import net.minecraft.network.syncher.SynchedEntityData;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.tags.TagKey;
import net.minecraft.util.Mth;
import net.minecraft.world.BossEvent;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityDimensions;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.Pose;
import net.minecraft.world.entity.ai.attributes.AttributeModifier;
import net.minecraft.world.entity.ai.attributes.AttributeSupplier;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.ai.goal.FloatGoal;
import net.minecraft.world.entity.ai.goal.WaterAvoidingRandomStrollGoal;
import net.minecraft.world.entity.ai.goal.target.HurtByTargetGoal;
import net.minecraft.world.entity.ai.goal.target.NearestAttackableTargetGoal;
import net.minecraft.world.entity.monster.Monster;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.entity.projectile.Projectile;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.entity.PartEntity;
import net.minecraftforge.event.ForgeEventFactory;

public final class TyrantEntity extends EncounterMob {
    public static final int PUNCH = 1, SHOVE = 2, CHARGE = 3, BREAK = 4, RAGE = 5;
    public static final int PUNCH_LEFT = 6, SHOVE_LEFT = 7, THROW = 8, SLASH = 9, SLASH_LEFT = 10;
    public static final Vec3 EYE_LOCAL_CENTER = new Vec3(-12.8 / 16, 52.0 / 16, 8.84 / 16);
    public static final String[] EXPOSURE_BONES = { "root", "pelvis", "torso", "chest", "tyrant_eye" };
    public static final TagKey<Block> BREAKABLE = TagKey.create(Registries.BLOCK, new ResourceLocation(ResidentEvilMod.MOD_ID, "tyrant_breakable"));
    private static final EntityDataAccessor<Boolean> RAGING = SynchedEntityData.defineId(TyrantEntity.class, EntityDataSerializers.BOOLEAN);
    private static final UUID SPEED_BONUS = UUID.fromString("03d54d40-b53a-46f8-a393-842c3b1e980a");
    private static final UUID ARMOR_PENALTY = UUID.fromString("0be6f004-b7b4-4057-9c87-87de4f408abf");
    private final EyePart eye;
    private final PartEntity<?>[] parts;
    private boolean resolvingWeakHit;
    private boolean rageTriggered;
    private int chargeCooldown;
    private int throwCooldown;
    private int breakCooldown;
    private int closeAttacks;

    public TyrantEntity(EntityType<? extends Monster> type, Level level) {
        super(type, level);
        eye = new EyePart(this);
        parts = new PartEntity<?>[] { eye };
        setId(ENTITY_COUNTER.getAndAdd(2) + 1);
        enableBossBar(BossEvent.BossBarColor.RED);
        setMaxUpStep(1.0F);
    }

    public static AttributeSupplier.Builder attributes() {
        return Monster.createMonsterAttributes().add(Attributes.MAX_HEALTH, CommonConfig.TYRANT_HEALTH)
                .add(Attributes.ARMOR, 12).add(Attributes.MOVEMENT_SPEED, CommonConfig.TYRANT_MOVE_SPEED)
                .add(Attributes.ATTACK_DAMAGE, CommonConfig.TYRANT_PUNCH_DAMAGE).add(Attributes.FOLLOW_RANGE, 64)
                .add(Attributes.KNOCKBACK_RESISTANCE, 0.9);
    }

    @Override
    protected void defineSynchedData() {
        super.defineSynchedData();
        entityData.define(RAGING, false);
    }

    @Override
    protected void registerGoals() {
        goalSelector.addGoal(0, new FloatGoal(this));
        goalSelector.addGoal(1, new TyrantPursuitGoal(this));
        goalSelector.addGoal(6, new WaterAvoidingRandomStrollGoal(this, 0.65));
        targetSelector.addGoal(1, new HurtByTargetGoal(this));
        NearestAttackableTargetGoal<Player> tracking = new NearestAttackableTargetGoal<>(this, Player.class, 10, true, false, EncounterMob::validTarget);
        tracking.setUnseenMemoryTicks(1200);
        targetSelector.addGoal(2, tracking);
    }

    public boolean isRaging() { return entityData.get(RAGING); }

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

    public Vec3 eyeCenter() { return EYE_LOCAL_CENTER.yRot(-yBodyRot * Mth.DEG_TO_RAD).add(position()); }

    @Override
    public void setHealth(float health) {
        super.setHealth(health);
        // Capture the crossing before healing or the current attack can defer the phase change.
        if (!level().isClientSide && getHealth() > 0
                && getHealth() <= getMaxHealth() * CommonConfig.TYRANT_RAGE_THRESHOLD) rageTriggered = true;
    }

    public boolean canThrowDebris() {
        return isAlive() && !rageTriggered && !isRaging()
                && getHealth() > getMaxHealth() * CommonConfig.TYRANT_RAGE_THRESHOLD;
    }

    private void applyPhaseAttributes() {
        var speed = getAttribute(Attributes.MOVEMENT_SPEED);
        var armor = getAttribute(Attributes.ARMOR);
        if (speed != null) {
            speed.removeModifier(SPEED_BONUS);
            if (isRaging()) speed.addTransientModifier(new AttributeModifier(SPEED_BONUS, "Limiter break", 0.25, AttributeModifier.Operation.MULTIPLY_TOTAL));
        }
        if (armor != null) {
            armor.removeModifier(ARMOR_PENALTY);
            if (isRaging()) armor.addTransientModifier(new AttributeModifier(ARMOR_PENALTY, "Discarded limiter coat", CommonConfig.TYRANT_RAGE_ARMOR_PENALTY, AttributeModifier.Operation.ADDITION));
        }
    }

    public void updatePhase() {
        if (level().isClientSide || !isAlive() || isRaging()) return;
        if (getHealth() <= getMaxHealth() * CommonConfig.TYRANT_RAGE_THRESHOLD) rageTriggered = true;
        if (!rageTriggered || attacking()) return;
        entityData.set(RAGING, true);
        applyPhaseAttributes();
        startAttack(RAGE, 40, CommonConfig.TYRANT_RECOVERY, CommonConfig.TYRANT_TRANSITION_SPEED);
        playSound(ModSounds.RAGE.get(), 1.6F, 0.7F);
    }

    @Override
    public void tick() {
        super.tick();
        Vec3 center = eyeCenter();
        eye.setPos(center.x, center.y - eye.getBbHeight() * 0.5, center.z);
        if (level().isClientSide || !isAlive()) return;
        updatePhase();
        chargeCooldown = Math.max(0, chargeCooldown - 1);
        throwCooldown = Math.max(0, throwCooldown - 1);
        breakCooldown = Math.max(0, breakCooldown - 1);
        if (!validTarget(getTarget())) setTarget(null);
        if (isNoAi() || getTarget() == null || attacking() || cooldown > 0) return;
        double distance = distanceTo(getTarget());
        if (breakCooldown == 0 && hasBreakableAhead()) {
            startAttack(BREAK, 28, CommonConfig.TYRANT_RECOVERY, combatSpeed());
            breakCooldown = CommonConfig.TYRANT_BREAK_COOLDOWN;
        } else if (canThrowDebris() && throwCooldown == 0 && distance >= CommonConfig.TYRANT_THROW_MIN_RANGE
                && distance <= CommonConfig.TYRANT_THROW_MAX_RANGE && hasLineOfSight(getTarget())) {
            startAttack(THROW, 36, 8, 1.25);
            throwCooldown = CommonConfig.TYRANT_THROW_COOLDOWN;
        } else if (distance >= 4 && distance <= 16 && chargeCooldown == 0 && onGround() && hasLineOfSight(getTarget())) {
            startAttack(CHARGE, 40, CommonConfig.TYRANT_RECOVERY, combatSpeed());
            chargeCooldown = CommonConfig.TYRANT_CHARGE_COOLDOWN;
        } else if (distance <= 3.1 && hasLineOfSight(getTarget())) {
            int skill = nextMeleeAttack();
            startAttack(skill, isSweep(skill) ? 24 : 32, CommonConfig.TYRANT_RECOVERY, combatSpeed());
        }
    }

    int nextMeleeAttack() {
        int step = closeAttacks++;
        if (isRaging()) return step % 2 == 0 ? SLASH : SLASH_LEFT;
        return switch (step % 4) { case 1 -> PUNCH_LEFT; case 2 -> SHOVE; case 3 -> SHOVE_LEFT; default -> PUNCH; };
    }

    private boolean isSweep(int skill) { return skill == SHOVE || skill == SHOVE_LEFT || skill == SLASH || skill == SLASH_LEFT; }
    private double combatSpeed() { return isRaging() ? CommonConfig.TYRANT_RAGE_ATTACK_SPEED : CommonConfig.TYRANT_ATTACK_SPEED; }
    private float damage(float amount) { return isRaging() ? amount * CommonConfig.TYRANT_RAGE_DAMAGE_MULTIPLIER : amount; }

    @Override
    protected void attackFrame(int attack, int tick) {
        int hitFrame = isSweep(attack) ? 10 : attack == CHARGE || attack == THROW ? 20 : 16;
        if (attack != RAGE && attack != BREAK && tick < attackFrameAt(hitFrame)) {
            trackWindup(attack == THROW ? 4 : 10);
            if (attack == PUNCH || attack == PUNCH_LEFT || isSweep(attack)) advanceTowardTarget(CommonConfig.TYRANT_PRESSURE_STEP, 1.8);
        }
        if ((attack == PUNCH || attack == PUNCH_LEFT) && tick == attackFrameAt(16)) strike(3.2, 110, damage(CommonConfig.TYRANT_PUNCH_DAMAGE), 0.6);
        if ((attack == SHOVE || attack == SHOVE_LEFT) && tick == attackFrameAt(10)) strike(3.4, 240, damage(CommonConfig.TYRANT_SHOVE_DAMAGE), 1.0);
        if ((attack == SLASH || attack == SLASH_LEFT) && tick == attackFrameAt(10)) strike(3.6, 160, damage(CommonConfig.TYRANT_PUNCH_DAMAGE), 0.6);
        if (attack == THROW && tick == attackFrameAt(20)) throwDebris();
        if (attack == BREAK && tick == attackFrameAt(14)) breakSoftObstacles();
        if (attack == CHARGE && tick >= attackFrameAt(20) && tick <= attackFrameAt(35)) {
            if (!horizontalCollision) {
                Vec3 forward = forward();
                setDeltaMovement(forward.x * 0.95, getDeltaMovement().y, forward.z * 0.95);
                hasImpulse = true;
            } else {
                setDeltaMovement(0, getDeltaMovement().y, 0);
            }
            strike(1.9, 100, damage(CommonConfig.TYRANT_CHARGE_DAMAGE), 1.5);
        }
        if (attack == CHARGE && tick == attackFrameAt(35) + 1) setDeltaMovement(0, getDeltaMovement().y, 0);
    }

    void throwDebris() {
        if (level().isClientSide || !canThrowDebris() || !validTarget(getTarget()) || !hasLineOfSight(getTarget())) return;
        Vec3 origin = position().add(0, 2.8, 0).add(forward().scale(0.9));
        // Do not materialize rocks on the other side of a nearby wall.
        if (level().clip(new ClipContext(position().add(0, 2.8, 0), origin,
                ClipContext.Block.COLLIDER, ClipContext.Fluid.NONE, this)).getType() != HitResult.Type.MISS) return;
        Vec3 aim = getTarget().getBoundingBox().getCenter().subtract(origin);
        double flight = aim.length() / 1.25;
        for (int i = -1; i <= 1; i++) {
            var rock = new TyrantDebrisEntity(this);
            rock.setPos(origin);
            Vec3 direction = aim.add(0, 0.0125 * flight * flight, 0).yRot(i * 0.07F);
            rock.shoot(direction.x, direction.y, direction.z, 1.25F, 0);
            level().addFreshEntity(rock);
        }
        playSound(ModSounds.IMPACT.get(), 1.4F, 0.6F);
    }

    private boolean attackIntersectsEye(DamageSource source) {
        if (!isRaging()) return false;
        Vec3 start;
        Vec3 end;
        if (source.getDirectEntity() instanceof Projectile projectile) {
            start = projectile.position();
            end = start.add(projectile.getDeltaMovement());
        } else if (source.getDirectEntity() instanceof LivingEntity attacker && attacker.distanceTo(this) < 6) {
            start = attacker.getEyePosition();
            end = start.add(attacker.getViewVector(1).scale(6));
        } else return false;
        AABB eyeBox = eye.getBoundingBox();
        AABB bodyBox = getBoundingBox();
        var eyeHit = eyeBox.contains(start) ? java.util.Optional.of(start) : eyeBox.clip(start, end);
        var bodyHit = bodyBox.contains(start) ? java.util.Optional.of(start) : bodyBox.clip(start, end);
        return eyeHit.isPresent() && (bodyHit.isEmpty() || start.distanceToSqr(eyeHit.get()) <= start.distanceToSqr(bodyHit.get()) + 1.0E-7);
    }

    @Override
    public boolean hurt(DamageSource source, float amount) { return takeHit(source, amount, attackIntersectsEye(source)); }

    private boolean takeHit(DamageSource source, float amount, boolean weakHit) {
        boolean bonus = weakHit && isRaging();
        boolean hit;
        resolvingWeakHit = bonus;
        try {
            hit = super.hurt(source, amount);
        } finally {
            resolvingWeakHit = false;
        }
        if (hit && bonus && level() instanceof ServerLevel server) {
            Vec3 center = eyeCenter();
            server.sendParticles(ParticleTypes.DAMAGE_INDICATOR, center.x, center.y, center.z, 8, 0.15, 0.15, 0.15, 0.05);
            playSound(ModSounds.EYE_OPEN.get(), 1.2F, 1.6F);
        }
        return hit;
    }

    @Override
    protected float getDamageAfterMagicAbsorb(DamageSource source, float amount) {
        float reduced = super.getDamageAfterMagicAbsorb(source, amount);
        return resolvingWeakHit ? reduced * (float) CommonConfig.TYRANT_EYE_MULTIPLIER : reduced;
    }

    private Iterable<BlockPos> obstacleSection(Vec3 direction) {
        Vec3 horizontal = new Vec3(direction.x, 0, direction.z).normalize();
        // A bounded body-width section also finds the sides of an existing narrow hole.
        AABB section = getBoundingBox().deflate(0.0001).move(horizontal);
        return BlockPos.betweenClosed(BlockPos.containing(section.minX, section.minY, section.minZ),
                BlockPos.containing(section.maxX, section.maxY, section.maxZ));
    }

    private boolean canBreak(BlockPos pos) {
        BlockState state = level().getBlockState(pos);
        float hardness = state.getDestroySpeed(level(), pos);
        return pos.getY() >= blockPosition().getY() && state.is(BREAKABLE) && !state.hasBlockEntity()
                && !state.getCollisionShape(level(), pos).isEmpty()
                && hardness >= 0 && hardness <= CommonConfig.TYRANT_MAX_BREAK_HARDNESS;
    }

    public boolean hasBreakableAhead() {
        if (!validTarget(getTarget()) || !CommonConfig.TYRANT_BREAK_BLOCKS.get()
                || !ForgeEventFactory.getMobGriefingEvent(level(), this)) return false;
        Vec3 direction = getTarget().position().subtract(position());
        for (BlockPos pos : obstacleSection(direction)) if (canBreak(pos)) return true;
        return false;
    }

    public void breakSoftObstacles() {
        if (level().isClientSide || !isAlive() || !validTarget(getTarget())
                || !CommonConfig.TYRANT_BREAK_BLOCKS.get() || !ForgeEventFactory.getMobGriefingEvent(level(), this)) return;
        int broken = 0;
        for (BlockPos pos : obstacleSection(forward())) {
            if (broken >= CommonConfig.TYRANT_BREAK_LIMIT) break;
            if (canBreak(pos) && level().destroyBlock(pos, true, this)) broken++;
        }
        playSound(ModSounds.IMPACT.get(), 1.3F, 0.7F);
    }

    @Override
    protected void playStepSound(BlockPos pos, BlockState state) { playSound(ModSounds.HEAVY_STEP.get(), 0.75F, 0.7F); }

    @Override
    protected String attackAnimation(int attack) {
        return switch (attack) { case PUNCH_LEFT -> "punch_left"; case SHOVE -> "shove"; case SHOVE_LEFT -> "shove_left";
            case SLASH -> "slash"; case SLASH_LEFT -> "slash_left"; case THROW -> "throw";
            case CHARGE -> "charge"; case BREAK -> "break"; case RAGE -> "rage"; default -> "punch"; };
    }

    @Override
    public String assetId() { return "tyrant"; }

    @Override
    public int deathDurationTicks() { return 60; }

    @Override
    public void addAdditionalSaveData(CompoundTag tag) {
        super.addAdditionalSaveData(tag);
        tag.putBoolean("TyrantRaging", isRaging());
        tag.putBoolean("TyrantRageTriggered", rageTriggered || isRaging());
        tag.putInt("TyrantThrowCooldown", throwCooldown);
        tag.putInt("TyrantChargeCooldown", chargeCooldown);
    }

    @Override
    public void readAdditionalSaveData(CompoundTag tag) {
        super.readAdditionalSaveData(tag);
        entityData.set(RAGING, tag.getBoolean("TyrantRaging"));
        rageTriggered = tag.getBoolean("TyrantRageTriggered") || isRaging()
                || getHealth() <= getMaxHealth() * CommonConfig.TYRANT_RAGE_THRESHOLD;
        throwCooldown = Mth.clamp(tag.getInt("TyrantThrowCooldown"), 0, CommonConfig.TYRANT_THROW_COOLDOWN);
        chargeCooldown = Mth.clamp(tag.getInt("TyrantChargeCooldown"), 0, CommonConfig.TYRANT_CHARGE_COOLDOWN);
        applyPhaseAttributes();
    }

    public static final class EyePart extends PartEntity<TyrantEntity> {
        public EyePart(TyrantEntity parent) { super(parent); refreshDimensions(); }

        @Override
        public EntityDimensions getDimensions(Pose pose) { return EntityDimensions.fixed(0.5F, 0.5F); }
        @Override
        protected void defineSynchedData() { }
        @Override
        protected void readAdditionalSaveData(CompoundTag tag) { }
        @Override
        protected void addAdditionalSaveData(CompoundTag tag) { }
        @Override
        public boolean isPickable() { return getParent().isAlive() && getParent().isRaging(); }
        @Override
        public boolean is(Entity other) { return this == other || getParent() == other; }
        @Override
        public boolean hurt(DamageSource source, float amount) {
            return isPickable() && !isInvulnerableTo(source) && getParent().takeHit(source, amount, true);
        }
    }
}
