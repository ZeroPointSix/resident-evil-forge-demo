package com.zeropointsix.redemo.entity.ai;

import com.zeropointsix.redemo.ResidentEvilMod;
import com.zeropointsix.redemo.entity.EncounterMob;
import com.zeropointsix.redemo.entity.LickerEntity;
import java.util.Map;
import java.util.WeakHashMap;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.event.entity.ProjectileImpactEvent;
import net.minecraftforge.event.entity.living.LivingFallEvent;
import net.minecraftforge.event.entity.living.LivingHurtEvent;
import net.minecraftforge.event.level.BlockEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

@Mod.EventBusSubscriber(modid = ResidentEvilMod.MOD_ID)
public final class NoiseEvents {
    private static final Map<Player, Vec3> PREVIOUS_POSITIONS = new WeakHashMap<>();
    private NoiseEvents() { }

    public static void emit(Level level, Vec3 position, LivingEntity source, double radius) {
        if (!(level instanceof ServerLevel)) return;
        if (source instanceof Player && !EncounterMob.validTarget(source)) return;
        AABB area = new AABB(position, position).inflate(radius);
        for (LickerEntity licker : level.getEntitiesOfClass(LickerEntity.class, area)) licker.hear(position, source, radius);
    }

    @SubscribeEvent
    public static void footsteps(TickEvent.PlayerTickEvent event) {
        Player p = event.player;
        if (event.phase != TickEvent.Phase.END || p.level().isClientSide) return;
        Vec3 previous = PREVIOUS_POSITIONS.put(p, p.position());
        if (previous == null || p.isCrouching() || p.isShiftKeyDown() || !p.onGround() || !EncounterMob.validTarget(p)) return;
        double moved = p.position().distanceToSqr(previous);
        if (moved > 0.0005 && moved < 25 && p.tickCount % (p.isSprinting() ? 6 : 12) == 0) emit(p.level(), p.position(), p, p.isSprinting() ? 20 : 9);
    }

    @SubscribeEvent
    public static void landed(LivingFallEvent event) {
        if (event.getEntity() instanceof Player p && event.getDistance() > 0.5F) emit(p.level(), p.position(), p, p.isCrouching() ? 5 : 14);
    }

    @SubscribeEvent
    public static void broken(BlockEvent.BreakEvent event) {
        emit(event.getPlayer().level(), Vec3.atCenterOf(event.getPos()), event.getPlayer(), 16);
    }

    @SubscribeEvent
    public static void placed(BlockEvent.EntityPlaceEvent event) {
        if (event.getEntity() instanceof LivingEntity source) emit(source.level(), Vec3.atCenterOf(event.getPos()), source, 12);
    }

    @SubscribeEvent
    public static void hurt(LivingHurtEvent event) {
        if (event.getEntity() instanceof Player p) emit(p.level(), p.position(), p, 16);
    }

    @SubscribeEvent
    public static void projectile(ProjectileImpactEvent event) {
        if (event.getRayTraceResult().getType() == net.minecraft.world.phys.HitResult.Type.BLOCK) {
            LivingEntity source = event.getProjectile().getOwner() instanceof LivingEntity living ? living : null;
            emit(event.getProjectile().level(), event.getRayTraceResult().getLocation(), source, 18);
        }
    }
}
