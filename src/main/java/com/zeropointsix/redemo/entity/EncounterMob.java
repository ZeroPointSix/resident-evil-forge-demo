package com.zeropointsix.redemo.entity;

import com.zeropointsix.redemo.config.CommonConfig;
import com.zeropointsix.redemo.registry.ModSounds;
import java.util.HashSet;
import java.util.Set;
import java.util.UUID;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.syncher.EntityDataAccessor;
import net.minecraft.network.syncher.EntityDataSerializers;
import net.minecraft.network.syncher.SynchedEntityData;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.level.ServerBossEvent;
import net.minecraft.sounds.SoundEvent;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.util.Mth;
import net.minecraft.world.BossEvent;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.monster.Monster;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.Vec3;
import software.bernie.geckolib.animatable.GeoEntity;
import software.bernie.geckolib.core.animatable.instance.AnimatableInstanceCache;
import software.bernie.geckolib.core.animation.AnimatableManager;
import software.bernie.geckolib.core.animation.AnimationController;
import software.bernie.geckolib.core.animation.RawAnimation;
import software.bernie.geckolib.util.GeckoLibUtil;

public abstract class EncounterMob extends Monster implements GeoEntity {
    private static final EntityDataAccessor<Integer> ATTACK = SynchedEntityData.defineId(EncounterMob.class, EntityDataSerializers.INT);
    private static final EntityDataAccessor<Integer> ATTACK_TICK = SynchedEntityData.defineId(EncounterMob.class, EntityDataSerializers.INT);
    private final AnimatableInstanceCache animationCache = GeckoLibUtil.createInstanceCache(this);
    protected final Set<UUID> attackHits = new HashSet<>();
    protected int attackDuration;
    protected int cooldown;
    protected float attackYaw;
    private ServerBossEvent bossBar;

    protected EncounterMob(EntityType<? extends Monster> type, Level level) {
        super(type, level);
        setPersistenceRequired();
        xpReward = 30;
    }

    protected void enableBossBar(BossEvent.BossBarColor color) {
        bossBar = new ServerBossEvent(getDisplayName(), color, BossEvent.BossBarOverlay.PROGRESS);
        xpReward = 100;
    }

    @Override
    protected void defineSynchedData() {
        super.defineSynchedData();
        entityData.define(ATTACK, 0);
        entityData.define(ATTACK_TICK, 0);
    }

    public int attack() { return entityData.get(ATTACK); }
    public int attackTick() { return entityData.get(ATTACK_TICK); }
    public boolean attacking() { return attack() != 0; }
    public abstract String assetId();
    public abstract int deathDurationTicks();
    protected abstract String attackAnimation(int attack);
    protected abstract void attackFrame(int attack, int tick);

    protected void startAttack(int attack, int duration, int recovery) {
        if (level().isClientSide || attacking() || !isAlive()) return;
        attackYaw = getYRot();
        if (getTarget() != null) {
            Vec3 d = getTarget().position().subtract(position());
            attackYaw = (float) (Mth.atan2(d.z, d.x) * 180 / Math.PI) - 90;
        }
        setYRot(attackYaw);
        setYHeadRot(attackYaw);
        yBodyRot = attackYaw;
        entityData.set(ATTACK, attack);
        entityData.set(ATTACK_TICK, 0);
        attackDuration = duration;
        cooldown = duration + recovery;
        attackHits.clear();
        getNavigation().stop();
    }

    @Override
    public void tick() {
        super.tick();
        if (level().isClientSide) return;
        if (!isAlive()) {
            entityData.set(ATTACK, 0);
            return;
        }
        if (cooldown > 0) cooldown--;
        if (attacking()) {
            getNavigation().stop();
            setYRot(attackYaw);
            setYHeadRot(attackYaw);
            yBodyRot = attackYaw;
            int frame = attackTick() + 1;
            entityData.set(ATTACK_TICK, frame);
            attackFrame(attack(), frame);
            if (frame >= attackDuration) {
                entityData.set(ATTACK, 0);
                entityData.set(ATTACK_TICK, 0);
                onAttackFinished();
            }
        }
        if (bossBar != null) {
            bossBar.setProgress(Mth.clamp(getHealth() / getMaxHealth(), 0, 1));
            bossBar.setName(getDisplayName());
        }
    }

    protected void onAttackFinished() { }

    protected double animationSpeed() { return 1; }

    public static boolean validTarget(LivingEntity target) {
        return target != null && target.isAlive() && (!(target instanceof Player p) || (!p.isCreative() && !p.isSpectator()));
    }

    protected Vec3 forward() {
        double r = Math.toRadians(attackYaw);
        return new Vec3(-Math.sin(r), 0, Math.cos(r));
    }

    protected boolean clearAttackLine(LivingEntity victim) {
        return level().clip(new ClipContext(getEyePosition(), victim.getBoundingBox().getCenter(), ClipContext.Block.COLLIDER, ClipContext.Fluid.NONE, this)).getType() == HitResult.Type.MISS;
    }

    protected void strike(double range, double arcDegrees, float damage, double knockback) {
        Vec3 direction = forward();
        for (LivingEntity victim : level().getEntitiesOfClass(LivingEntity.class, getBoundingBox().inflate(range, 1.5, range))) {
            if (victim == this || !validTarget(victim) || (victim != getTarget() && !(victim instanceof Player))) continue;
            Vec3 offset = victim.position().subtract(position());
            double planar = Math.sqrt(offset.x * offset.x + offset.z * offset.z);
            if (planar > range + victim.getBbWidth() * 0.5 || Math.abs(offset.y) > 2.5) continue;
            if (planar > 0.1 && direction.dot(new Vec3(offset.x, 0, offset.z).normalize()) < Math.cos(Math.toRadians(arcDegrees / 2))) continue;
            if (!clearAttackLine(victim) || attackHits.contains(victim.getUUID())) continue;
            if (victim.hurt(damageSources().mobAttack(this), damage * CommonConfig.DAMAGE_SCALE.get().floatValue())) {
                attackHits.add(victim.getUUID());
                if (knockback > 0) victim.knockback(knockback, -offset.x, -offset.z);
                playSound(ModSounds.IMPACT.get(), 1, 0.8F);
            }
        }
    }

    @Override
    public void startSeenByPlayer(ServerPlayer player) {
        super.startSeenByPlayer(player);
        if (bossBar != null && isAlive()) bossBar.addPlayer(player);
    }

    @Override
    public void stopSeenByPlayer(ServerPlayer player) {
        super.stopSeenByPlayer(player);
        if (bossBar != null) bossBar.removePlayer(player);
    }

    @Override
    public void die(DamageSource source) {
        super.die(source);
        getNavigation().stop();
        setTarget(null);
        entityData.set(ATTACK, 0);
        entityData.set(ATTACK_TICK, 0);
        if (bossBar != null) bossBar.removeAllPlayers();
    }

    @Override
    protected void tickDeath() {
        deathTime++;
        if (deathTime >= deathDurationTicks() && !level().isClientSide && !isRemoved()) {
            level().broadcastEntityEvent(this, (byte) 60);
            remove(RemovalReason.KILLED);
        }
    }

    @Override
    public void remove(RemovalReason reason) {
        if (bossBar != null) bossBar.removeAllPlayers();
        super.remove(reason);
    }

    @Override
    public void readAdditionalSaveData(CompoundTag tag) {
        super.readAdditionalSaveData(tag);
        entityData.set(ATTACK, 0);
        entityData.set(ATTACK_TICK, 0);
        setNoGravity(false);
    }

    @Override
    protected SoundEvent getHurtSound(DamageSource source) { return SoundEvents.RAVAGER_HURT; }

    @Override
    protected SoundEvent getDeathSound() { return SoundEvents.RAVAGER_DEATH; }

    @Override
    public void registerControllers(AnimatableManager.ControllerRegistrar controllers) {
        controllers.add(new AnimationController<>(this, "action", 0, state -> {
            state.getController().setAnimationSpeed(animationSpeed());
            String clip = !isAlive() ? "death" : attacking() ? attackAnimation(attack()) : hurtTime > 0 ? "hurt" : state.isMoving() ? "walk" : "idle";
            String name = "animation." + assetId() + "." + clip;
            boolean loop = clip.equals("idle") || clip.equals("walk");
            return state.setAndContinue(loop ? RawAnimation.begin().thenLoop(name) : RawAnimation.begin().thenPlay(name));
        }));
    }

    @Override
    public AnimatableInstanceCache getAnimatableInstanceCache() { return animationCache; }
}
