package com.zeropointsix.redemo.entity;

import com.mojang.logging.LogUtils;
import com.zeropointsix.redemo.ResidentEvilMod;
import com.zeropointsix.redemo.registry.ModEntities;
import com.zeropointsix.redemo.registry.ModItems;
import net.minecraft.client.Minecraft;
import net.minecraft.client.Screenshot;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.GameRules;
import net.minecraft.world.level.GameType;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Opt-in, deterministic capture in a real integrated Minecraft client. */
@Mod.EventBusSubscriber(modid = ResidentEvilMod.MOD_ID, value = Dist.CLIENT)
public final class ClientEvidenceCapture {
    private static final String[] NAMES = {"licker", "tyrant", "g1_birkin"};
    private static int ticks;
    private static EncounterMob mob;
    private static LivingEntity target;

    private ClientEvidenceCapture() { }

    @SubscribeEvent
    public static void tick(TickEvent.ClientTickEvent event) {
        if (!Boolean.getBoolean("re_demo.captureEvidence") || event.phase != TickEvent.Phase.END) return;
        Minecraft mc = Minecraft.getInstance();
        if (mc.level == null || mc.player == null || mc.getSingleplayerServer() == null) return;
        mc.options.pauseOnLostFocus = false;
        mc.options.hideGui = false;
        mc.options.fov().set(55);
        int frame = ticks++;
        if (frame >= 1260) {
            LogUtils.getLogger().info("RE_DEMO_EVIDENCE_COMPLETE frames={}", frame);
            mc.stop();
            return;
        }
        if (frame >= 1200) return;
        int scene = frame / 400;
        int sceneTick = frame % 400;
        var server = mc.getSingleplayerServer();
        var playerId = mc.player.getUUID();
        server.execute(() -> {
            ServerLevel level = server.overworld();
            if (sceneTick == 0) {
                level.getEntitiesOfClass(LivingEntity.class, new AABB(-15, 75, -15, 15, 95, 15), e -> !(e instanceof net.minecraft.world.entity.player.Player)).forEach(e -> e.discard());
                for (int x = -10; x <= 10; x++) for (int z = -8; z <= 12; z++) {
                    level.setBlockAndUpdate(new BlockPos(x, 80, z), ((x + z) % 2 == 0 ? Blocks.SMOOTH_STONE : Blocks.STONE).defaultBlockState());
                    for (int y = 81; y <= 86; y++) level.setBlockAndUpdate(new BlockPos(x, y, z), Blocks.AIR.defaultBlockState());
                }
                level.setDayTime(6000);
                level.setWeatherParameters(6000, 0, false, false);
                level.getGameRules().getRule(GameRules.RULE_DOMOBSPAWNING).set(false, server);
                level.getGameRules().getRule(GameRules.RULE_DODAYLIGHTCYCLE).set(false, server);
                mob = switch (scene) {
                    case 0 -> ModEntities.LICKER.get().create(level);
                    case 1 -> ModEntities.TYRANT.get().create(level);
                    default -> ModEntities.G1_BIRKIN.get().create(level);
                };
                mob.moveTo(0, 81, 0, 0, 0);
                mob.setNoAi(true);
                mob.setPersistenceRequired();
                mob.setCustomName(Component.literal(NAMES[scene]));
                mob.setCustomNameVisible(true);
                level.addFreshEntity(mob);
                var dummy = EntityType.HUSK.create(level);
                dummy.moveTo(0, 81, 2.7, 180, 0);
                dummy.setNoAi(true);
                dummy.setInvulnerable(true);
                dummy.getAttribute(Attributes.KNOCKBACK_RESISTANCE).setBaseValue(1);
                level.addFreshEntity(dummy);
                target = dummy;
                mob.setTarget(target);
                var player = server.getPlayerList().getPlayer(playerId);
                if (player != null) {
                    player.setGameMode(GameType.CREATIVE);
                    player.getAbilities().flying = true;
                    player.onUpdateAbilities();
                    player.teleportTo(level, 6.5, 82.4, 8, 137, 8);
                    player.getInventory().setItem(0, new ItemStack(ModItems.LICKER_EGG.get()));
                    player.getInventory().setItem(1, new ItemStack(ModItems.TYRANT_EGG.get()));
                    player.getInventory().setItem(2, new ItemStack(ModItems.G1_BIRKIN_EGG.get()));
                }
                LogUtils.getLogger().info("RE_DEMO_SCENE {}", NAMES[scene]);
            }
            if (mob == null) return;
            if (sceneTick == 40 || sceneTick == 110 || sceneTick == 180 || sceneTick == 250) {
                mob.setDeltaMovement(Vec3.ZERO);
                mob.moveTo(0, 81, 0, 0, 0);
                mob.setTarget(target);
                int skillIndex = (sceneTick - 40) / 70;
                int skill = switch (scene) {
                    case 0 -> new int[]{LickerEntity.CLAW, LickerEntity.LEAP, LickerEntity.TONGUE, LickerEntity.AMBUSH}[skillIndex];
                    case 1 -> new int[]{TyrantEntity.PUNCH, TyrantEntity.SHOVE, TyrantEntity.CHARGE, TyrantEntity.BREAK}[skillIndex];
                    default -> new int[]{G1BirkinEntity.SLAM, G1BirkinEntity.SWEEP, G1BirkinEntity.GRAB, G1BirkinEntity.RAGE}[skillIndex];
                };
                if (scene == 1 && skillIndex == 3) {
                    for (int x = -1; x <= 1; x++) for (int y = 81; y <= 83; y++) level.setBlockAndUpdate(new BlockPos(x, y, 1), Blocks.GLASS.defaultBlockState());
                }
                mob.startAttack(skill, 40, 5);
                LogUtils.getLogger().info("RE_DEMO_ATTACK {} skill={} sceneTick={}", NAMES[scene], skill, sceneTick);
            }
            if (sceneTick == 320) {
                target.discard();
                mob.hurt(mob.damageSources().genericKill(), 10000);
                LogUtils.getLogger().info("RE_DEMO_DEATH {} duration={}", NAMES[scene], mob.deathDurationTicks());
            }
        });
        if (sceneTick >= 20 && sceneTick % 4 == 0) {
            Screenshot.grab(mc.gameDirectory, String.format("re_demo_%s_%04d.png", NAMES[scene], sceneTick), mc.getMainRenderTarget(), message -> {});
        }
    }
}
