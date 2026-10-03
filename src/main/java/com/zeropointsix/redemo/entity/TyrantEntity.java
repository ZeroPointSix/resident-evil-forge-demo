package com.zeropointsix.redemo.entity;

import com.zeropointsix.redemo.ResidentEvilMod;
import com.zeropointsix.redemo.config.CommonConfig;
import com.zeropointsix.redemo.entity.ai.TyrantPursuitGoal;
import com.zeropointsix.redemo.registry.ModSounds;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.Registries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.syncher.EntityDataAccessor;
import net.minecraft.network.syncher.EntityDataSerializers;
import net.minecraft.network.syncher.SynchedEntityData;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.tags.TagKey;
import net.minecraft.world.BossEvent;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.ai.attributes.AttributeModifier;
import net.minecraft.world.entity.ai.attributes.AttributeSupplier;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.ai.goal.FloatGoal;
import net.minecraft.world.entity.ai.goal.WaterAvoidingRandomStrollGoal;
import net.minecraft.world.entity.ai.goal.target.HurtByTargetGoal;
import net.minecraft.world.entity.ai.goal.target.NearestAttackableTargetGoal;
import net.minecraft.world.entity.monster.Monster;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.ForgeEventFactory;

public final class TyrantEntity extends EncounterMob {
    public static final int PUNCH = 1, SHOVE = 2, CHARGE = 3, BREAK = 4, RAGE = 5;
    public static final TagKey<Block> BREAKABLE = TagKey.create(Registries.BLOCK, new ResourceLocation(ResidentEvilMod.MOD_ID, "tyrant_breakable"));
    private static final EntityDataAccessor<Boolean> RAGING = SynchedEntityData.defineId(TyrantEntity.class, EntityDataSerializers.BOOLEAN);
    private static final UUID SPEED_BONUS = UUID.fromString("03d54d40-b53a-46f8-a393-842c3b1e980a");
    private int chargeCooldown;
    private int breakCooldown;
    private int closeAttacks;

    public TyrantEntity(EntityType<? extends Monster> type, Level level) {
        super(type, level);
        enableBossBar(BossEvent.BossBarColor.RED);
        setMaxUpStep(1.0F);
    }

    public static AttributeSupplier.Builder attributes() {
        return Monster.createMonsterAttributes().add(Attributes.MAX_HEALTH, CommonConfig.TYRANT_HEALTH)
                .add(Attributes.ARMOR, 12).add(Attributes.MOVEMENT_SPEED, 0.22)
                .add(Attributes.ATTACK_DAMAGE, 16).add(Attributes.FOLLOW_RANGE, 64)
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

    public void updatePhase() {
        if (level().isClientSide || !isAlive() || isRaging() || attacking() || getHealth() > getMaxHealth() * 0.35F) return;
        entityData.set(RAGING, true);
        var speed = getAttribute(Attributes.MOVEMENT_SPEED);
        if (speed != null && speed.getModifier(SPEED_BONUS) == null) speed.addTransientModifier(new AttributeModifier(SPEED_BONUS, "Limiter break", 0.25, AttributeModifier.Operation.MULTIPLY_TOTAL));
        if (!attacking()) startAttack(RAGE, 40, 10);
        playSound(ModSounds.RAGE.get(), 1.6F, 0.7F);
    }

    @Override
    public void tick() {
        super.tick();
        if (level().isClientSide || !isAlive()) return;
        updatePhase();
        chargeCooldown = Math.max(0, chargeCooldown - 1);
        breakCooldown = Math.max(0, breakCooldown - 1);
        if (!validTarget(getTarget())) setTarget(null);
        if (isNoAi() || getTarget() == null || attacking() || cooldown > 0) return;
        double distance = distanceTo(getTarget());
        if (breakCooldown == 0 && hasBreakableAhead()) {
            startAttack(BREAK, scaled(28), 15);
            breakCooldown = 60;
        } else if (distance >= 4 && distance <= 10 && chargeCooldown == 0 && onGround() && hasLineOfSight(getTarget())) {
            startAttack(CHARGE, scaled(40), 35);
            chargeCooldown = 180;
        } else if (distance <= 2.7 && hasLineOfSight(getTarget())) {
            int skill = ++closeAttacks % 3 == 0 ? SHOVE : PUNCH;
            startAttack(skill, scaled(skill == SHOVE ? 24 : 32), 16);
        }
    }

    private int scaled(int ticks) { return isRaging() ? Math.max(1, Math.round(ticks * 0.8F)) : ticks; }
    private float damage(float amount) { return isRaging() ? amount * 1.2F : amount; }

    @Override
    protected void attackFrame(int attack, int tick) {
        if (attack == PUNCH && tick == scaled(16)) strike(2.8, 100, damage(16), 0.6);
        if (attack == SHOVE && tick == scaled(10)) strike(2.8, 150, damage(10), 1.8);
        if (attack == BREAK && tick == scaled(14)) breakSoftObstacles();
        if (attack == CHARGE && tick >= scaled(20) && tick <= scaled(35)) {
            if (!horizontalCollision) {
                Vec3 forward = forward();
                setDeltaMovement(forward.x * 0.65, getDeltaMovement().y, forward.z * 0.65);
                hasImpulse = true;
            }
            strike(1.9, 100, damage(22), 1.5);
        }
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
        return state.is(BREAKABLE) && !state.hasBlockEntity() && state.getDestroySpeed(level(), pos) >= 0;
    }

    public boolean hasBreakableAhead() {
        if (!CommonConfig.TYRANT_BREAK_BLOCKS.get() || !ForgeEventFactory.getMobGriefingEvent(level(), this)) return false;
        Vec3 direction = getTarget() == null ? getLookAngle() : getTarget().position().subtract(position());
        for (BlockPos pos : obstacleSection(direction)) if (canBreak(pos)) return true;
        return false;
    }

    public void breakSoftObstacles() {
        if (level().isClientSide || !CommonConfig.TYRANT_BREAK_BLOCKS.get() || !ForgeEventFactory.getMobGriefingEvent(level(), this)) return;
        for (BlockPos pos : obstacleSection(forward())) {
            if (canBreak(pos)) level().destroyBlock(pos, true, this);
        }
        playSound(ModSounds.IMPACT.get(), 1.3F, 0.7F);
    }

    @Override
    protected void playStepSound(BlockPos pos, BlockState state) { playSound(ModSounds.HEAVY_STEP.get(), 0.75F, 0.7F); }

    @Override
    protected double animationSpeed() { return isRaging() && attacking() && attack() != RAGE ? 1.25 : 1; }

    @Override
    protected String attackAnimation(int attack) {
        return switch (attack) { case SHOVE -> "shove"; case CHARGE -> "charge"; case BREAK -> "break"; case RAGE -> "rage"; default -> "punch"; };
    }

    @Override
    public String assetId() { return "tyrant"; }

    @Override
    public int deathDurationTicks() { return 60; }

    @Override
    public void readAdditionalSaveData(CompoundTag tag) {
        super.readAdditionalSaveData(tag);
        entityData.set(RAGING, false);
        var speed = getAttribute(Attributes.MOVEMENT_SPEED);
        if (speed != null) speed.removeModifier(SPEED_BONUS);
    }
}
