package com.zeropointsix.redemo.entity;

import com.zeropointsix.redemo.config.CommonConfig;
import com.zeropointsix.redemo.registry.ModEntities;
import net.minecraft.core.particles.BlockParticleOption;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.protocol.Packet;
import net.minecraft.network.protocol.game.ClientGamePacketListener;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.entity.projectile.ThrowableItemProjectile;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.phys.EntityHitResult;
import net.minecraft.world.phys.HitResult;
import net.minecraftforge.network.NetworkHooks;

public final class TyrantDebrisEntity extends ThrowableItemProjectile {
    private int lifetime;

    public TyrantDebrisEntity(EntityType<? extends TyrantDebrisEntity> type, Level level) {
        super(type, level);
    }

    public TyrantDebrisEntity(TyrantEntity owner) {
        this(ModEntities.TYRANT_DEBRIS.get(), owner.level());
        setOwner(owner);
    }

    @Override
    protected Item getDefaultItem() { return Items.COBBLESTONE; }

    @Override
    protected float getGravity() { return 0.025F; }

    @Override
    protected boolean canHitEntity(Entity candidate) {
        if (!super.canHitEntity(candidate) || !(getOwner() instanceof TyrantEntity owner)
                || !(candidate instanceof LivingEntity victim) || owner.isAlliedTo(victim)
                || !EncounterMob.validTarget(victim)) return false;
        return victim == owner.getTarget() || victim instanceof Player
                || victim instanceof Mob mob && mob.getTarget() == owner;
    }

    @Override
    protected void onHitEntity(EntityHitResult result) {
        super.onHitEntity(result);
        if (!level().isClientSide && getOwner() instanceof TyrantEntity owner && canHitEntity(result.getEntity())) {
            result.getEntity().hurt(damageSources().thrown(this, owner),
                    CommonConfig.TYRANT_DEBRIS_DAMAGE * CommonConfig.DAMAGE_SCALE.get().floatValue());
        }
    }

    @Override
    protected void onHit(HitResult result) {
        super.onHit(result);
        if (level() instanceof ServerLevel server) {
            server.sendParticles(new BlockParticleOption(ParticleTypes.BLOCK, Blocks.COBBLESTONE.defaultBlockState()),
                    getX(), getY(), getZ(), 12, 0.18, 0.18, 0.18, 0.06);
            discard();
        }
    }

    @Override
    public void tick() {
        if (!level().isClientSide && (++lifetime > 80 || !(getOwner() instanceof TyrantEntity owner)
                || !owner.isAlive() || owner.isRaging())) {
            discard();
            return;
        }
        super.tick();
    }

    @Override
    public void addAdditionalSaveData(CompoundTag tag) {
        super.addAdditionalSaveData(tag);
        tag.putInt("DebrisLifetime", lifetime);
    }

    @Override
    public void readAdditionalSaveData(CompoundTag tag) {
        super.readAdditionalSaveData(tag);
        lifetime = Math.max(0, tag.getInt("DebrisLifetime"));
    }

    @Override
    public Packet<ClientGamePacketListener> getAddEntityPacket() { return NetworkHooks.getEntitySpawningPacket(this); }
}
