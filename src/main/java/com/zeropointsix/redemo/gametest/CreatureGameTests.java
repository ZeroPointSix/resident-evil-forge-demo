package com.zeropointsix.redemo.gametest;

import com.mojang.authlib.GameProfile;
import com.zeropointsix.redemo.ResidentEvilMod;
import com.zeropointsix.redemo.entity.G1BirkinEntity;
import com.zeropointsix.redemo.entity.EncounterMob;
import com.zeropointsix.redemo.entity.LickerEntity;
import com.zeropointsix.redemo.entity.TyrantEntity;
import com.zeropointsix.redemo.entity.ai.NoiseEvents;
import com.zeropointsix.redemo.registry.ModEntities;
import com.zeropointsix.redemo.registry.ModItems;
import com.zeropointsix.redemo.registry.ModSounds;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.context.UseOnContext;
import net.minecraft.world.level.GameRules;
import net.minecraft.world.level.GameType;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.common.util.FakePlayer;
import net.minecraftforge.common.ForgeSpawnEggItem;
import net.minecraftforge.common.util.FakePlayerFactory;
import net.minecraftforge.gametest.GameTestHolder;
import net.minecraftforge.gametest.PrefixGameTestTemplate;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.registries.ForgeRegistries;

@GameTestHolder(ResidentEvilMod.MOD_ID)
@PrefixGameTestTemplate(false)
public final class CreatureGameTests {
    private CreatureGameTests() { }

    @GameTest(template = "empty", timeoutTicks = 40)
    public static void originalMusicIsRegistered(GameTestHelper h) {
        var id = new ResourceLocation(ResidentEvilMod.MOD_ID, "encounter_theme");
        h.assertTrue(ForgeRegistries.SOUND_EVENTS.getValue(id) == ModSounds.ENCOUNTER_THEME.get(),
                "Original music event must resolve through the live Forge sound registry");
        h.assertTrue(CreatureGameTests.class.getResource(
                "/assets/re_demo/sounds/music/containment_pulse.ogg") != null,
                "Original Ogg must be packaged in the running mod");
        h.succeed();
    }

    @GameTest(template = "empty", timeoutTicks = 40)
    public static void entitiesAndAttributes(GameTestHelper h) {
        var licker = h.spawn(ModEntities.LICKER.get(), new BlockPos(2, 1, 2));
        var tyrant = h.spawn(ModEntities.TYRANT.get(), new BlockPos(6, 1, 2));
        var birkin = h.spawn(ModEntities.G1_BIRKIN.get(), new BlockPos(10, 1, 2));
        h.assertTrue(licker.getMaxHealth() == 120 && tyrant.getMaxHealth() == 400 && birkin.getMaxHealth() == 480, "Configured health must match design");
        h.assertTrue(licker.getArmorValue() == 4 && tyrant.getArmorValue() == 12 && birkin.getArmorValue() == 8, "Armor must match design");
        h.assertTrue(birkin.getParts().length == 1 && birkin.eyePart().getId() == birkin.getId() + 1, "Eye hitbox must have a separate network ID");
        h.succeed();
    }

    @GameTest(template = "empty", timeoutTicks = 40)
    public static void spawnEggsCreateRealEntities(GameTestHelper h) {
        ServerLevel level = h.getLevel();
        FakePlayer player = FakePlayerFactory.get(level, new GameProfile(UUID.fromString("fa44d6ef-f113-4e49-b2fd-97a35bc6abb4"), "SpawnEggQA"));
        ItemStack old = player.getMainHandItem().copy();
        Vec3 oldPosition = player.position();
        try {
            checkEgg(h, player, ModItems.LICKER_EGG.get(), ModEntities.LICKER.get(), new BlockPos(2, 0, 2));
            checkEgg(h, player, ModItems.TYRANT_EGG.get(), ModEntities.TYRANT.get(), new BlockPos(6, 0, 2));
            checkEgg(h, player, ModItems.G1_BIRKIN_EGG.get(), ModEntities.G1_BIRKIN.get(), new BlockPos(10, 0, 2));
            h.succeed();
        } finally {
            player.setItemInHand(InteractionHand.MAIN_HAND, old);
            player.setPos(oldPosition);
        }
    }

    private static void checkEgg(GameTestHelper h, FakePlayer player, Item egg, EntityType<?> type, BlockPos relative) {
        BlockPos block = h.absolutePos(relative);
        h.getLevel().setBlockAndUpdate(block, Blocks.STONE.defaultBlockState());
        player.setPos(Vec3.atCenterOf(block.above(2)));
        player.setItemInHand(InteractionHand.MAIN_HAND, new ItemStack(egg));
        UseOnContext context = new UseOnContext(player, InteractionHand.MAIN_HAND, new BlockHitResult(Vec3.atCenterOf(block).add(0, 0.5, 0), Direction.UP, block, false));
        h.assertTrue(ForgeSpawnEggItem.fromEntityType(type) == egg, "Forge spawn egg must map to entity type");
        h.assertTrue(egg.useOn(context).consumesAction(), "Spawn egg use must succeed");
        h.assertTrue(!h.getLevel().getEntities(type, new AABB(block.above()).inflate(1), entity -> entity.isAlive()).isEmpty(), "Spawn egg must create a living entity");
    }

    @GameTest(template = "empty", timeoutTicks = 150)
    public static void lickerInvestigatesThenForgetsSound(GameTestHelper h) {
        LickerEntity licker = h.spawn(ModEntities.LICKER.get(), new BlockPos(2, 1, 2));
        licker.setNoAi(true);
        var target = h.spawn(EntityType.IRON_GOLEM, new BlockPos(7, 1, 2));
        target.setNoAi(true);
        licker.hear(target.position(), target, 16);
        h.assertTrue(licker.getTarget() == null && licker.investigationPoint() != null, "First sound must investigate, not visual aggro");
        licker.hear(target.position(), target, 16);
        h.assertTrue(licker.getTarget() == target, "Repeated sound must activate hunt");
        h.runAfterDelay(125, () -> {
            h.assertTrue(licker.getTarget() == null && licker.investigationPoint() == null, "Silent target must be forgotten");
            h.succeed();
        });
    }

    @GameTest(template = "empty", timeoutTicks = 40)
    public static void soundRadiusIsBounded(GameTestHelper h) {
        var licker = h.spawn(ModEntities.LICKER.get(), new BlockPos(2, 1, 2));
        Vec3 outside = licker.position().add(10, 0, 0);
        licker.hear(outside, null, 9);
        h.assertTrue(licker.investigationPoint() == null, "Distant quiet sound must not alert");
        NoiseEvents.emit(h.getLevel(), outside, null, 20);
        h.assertTrue(licker.investigationPoint() != null, "Loud sound inside radius must be recorded");
        h.succeed();
    }

    @GameTest(template = "empty", timeoutTicks = 40)
    public static void sneakingIsSilentButSprintIsAudible(GameTestHelper h) {
        var licker = h.spawn(ModEntities.LICKER.get(), new BlockPos(3, 1, 3));
        licker.setNoAi(true);
        FakePlayer player = FakePlayerFactory.get(h.getLevel(), new GameProfile(UUID.fromString("dcb3ab95-3d8f-45ba-9aa9-259b510228d2"), "HearingQA"));
        Vec3 oldPosition = player.position();
        boolean oldShift = player.isShiftKeyDown();
        boolean oldSprint = player.isSprinting();
        boolean oldGround = player.onGround();
        int oldTicks = player.tickCount;
        GameType oldMode = player.gameMode.getGameModeForPlayer();
        try {
            player.setGameMode(GameType.SURVIVAL);
            player.setOnGround(true);
            player.tickCount = 24;
            player.setPos(licker.position().add(3, 0, 0));
            NoiseEvents.footsteps(new TickEvent.PlayerTickEvent(TickEvent.Phase.END, player));
            player.setShiftKeyDown(true);
            player.setPos(player.position().add(0.2, 0, 0));
            NoiseEvents.footsteps(new TickEvent.PlayerTickEvent(TickEvent.Phase.END, player));
            h.assertTrue(licker.investigationPoint() == null, "Sneaking movement must not create footstep aggro");
            player.setShiftKeyDown(false);
            player.setSprinting(true);
            player.setPos(player.position().add(0.3, 0, 0));
            NoiseEvents.footsteps(new TickEvent.PlayerTickEvent(TickEvent.Phase.END, player));
            h.assertTrue(licker.investigationPoint() != null, "Sprinting movement must produce a detectable sound");
            h.succeed();
        } finally {
            player.setGameMode(oldMode);
            player.setShiftKeyDown(oldShift);
            player.setSprinting(oldSprint);
            player.setOnGround(oldGround);
            player.tickCount = oldTicks;
            player.setPos(oldPosition);
            NoiseEvents.clearFootstepHistory(player);
        }
    }

    @GameTest(template = "empty", timeoutTicks = 60)
    public static void lickerClawHasWindupAndSingleHit(GameTestHelper h) {
        var licker = h.spawn(ModEntities.LICKER.get(), new BlockPos(4, 1, 4));
        var target = h.spawn(EntityType.IRON_GOLEM, new BlockPos(4, 1, 6));
        target.setNoAi(true);
        target.setNoGravity(true);
        licker.setNoGravity(true);
        licker.getAttribute(Attributes.MOVEMENT_SPEED).setBaseValue(0);
        target.getAttribute(Attributes.KNOCKBACK_RESISTANCE).setBaseValue(1);
        licker.hear(target.position(), target, 16);
        licker.hear(target.position(), target, 16);
        float original = target.getHealth();
        h.runAfterDelay(5, () -> h.assertTrue(target.getHealth() == original, "Claw must not damage during telegraph"));
        h.runAfterDelay(14, () -> h.assertTrue(Math.abs(target.getHealth() - (original - 10)) < 0.001, "Claw must land one 10 damage hit at animation frame 9"));
        h.runAfterDelay(25, () -> {
            h.assertTrue(Math.abs(target.getHealth() - (original - 10)) < 0.001, "Same animation must never hit twice");
            h.succeed();
        });
    }

    @GameTest(template = "empty", timeoutTicks = 40)
    public static void tyrantPhaseHasNoStackingSpeedBonus(GameTestHelper h) {
        var tyrant = h.spawn(ModEntities.TYRANT.get(), new BlockPos(4, 1, 4));
        tyrant.setNoAi(true);
        double speed = tyrant.getAttributeValue(Attributes.MOVEMENT_SPEED);
        tyrant.setHealth(141);
        tyrant.updatePhase();
        h.assertTrue(!tyrant.isRaging(), "Limiter must not activate above 35 percent");
        tyrant.setHealth(140);
        tyrant.updatePhase();
        h.assertTrue(tyrant.isRaging(), "Limiter must activate at 35 percent");
        tyrant.updatePhase();
        h.assertTrue(Math.abs(tyrant.getAttributeValue(Attributes.MOVEMENT_SPEED) - speed * 1.25) < 0.00001, "Speed bonus must be exactly 25 percent and never stack");
        h.succeed();
    }

    @GameTest(template = "empty", timeoutTicks = 40)
    public static void tyrantRespectsMobGriefingAndBlockTag(GameTestHelper h) {
        var tyrant = h.spawn(ModEntities.TYRANT.get(), new BlockPos(4, 1, 4));
        tyrant.setNoAi(true);
        BlockPos glass = tyrant.blockPosition().south();
        BlockPos stone = glass.above();
        ServerLevel level = h.getLevel();
        boolean previous = level.getGameRules().getBoolean(GameRules.RULE_MOBGRIEFING);
        try {
            level.setBlockAndUpdate(glass, Blocks.GLASS.defaultBlockState());
            level.setBlockAndUpdate(stone, Blocks.STONE.defaultBlockState());
            level.getGameRules().getRule(GameRules.RULE_MOBGRIEFING).set(false, level.getServer());
            tyrant.breakSoftObstacles();
            h.assertTrue(level.getBlockState(glass).is(Blocks.GLASS), "mobGriefing false must preserve glass");
            level.getGameRules().getRule(GameRules.RULE_MOBGRIEFING).set(true, level.getServer());
            tyrant.breakSoftObstacles();
            h.assertTrue(level.getBlockState(glass).isAir(), "Whitelisted glass must break");
            h.assertTrue(level.getBlockState(stone).is(Blocks.STONE), "Non-whitelisted terrain must remain");
            h.succeed();
        } finally {
            level.getGameRules().getRule(GameRules.RULE_MOBGRIEFING).set(previous, level.getServer());
        }
    }

    @GameTest(template = "empty", timeoutTicks = 40)
    public static void g1EyeDamageIsExactly175Percent(GameTestHelper h) {
        G1BirkinEntity birkin = h.spawn(ModEntities.G1_BIRKIN.get(), new BlockPos(4, 1, 4));
        birkin.setNoAi(true);
        float health = birkin.getHealth();
        birkin.hurt(birkin.damageSources().generic(), 8);
        float bodyDamage = health - birkin.getHealth();
        birkin.invulnerableTime = 0;
        health = birkin.getHealth();
        birkin.eyePart().hurt(birkin.damageSources().generic(), 8);
        float closedEyeDamage = health - birkin.getHealth();
        birkin.invulnerableTime = 0;
        birkin.openWeakPoint(40);
        health = birkin.getHealth();
        birkin.eyePart().hurt(birkin.damageSources().generic(), 8);
        float openEyeDamage = health - birkin.getHealth();
        h.assertTrue(bodyDamage > 0, "Control body hit must deal damage");
        h.assertTrue(Math.abs(closedEyeDamage - bodyDamage) < 0.001, "Closed eye is not a weak point");
        h.assertTrue(Math.abs(openEyeDamage / bodyDamage - 1.75) < 0.001, "Open eye must multiply damage after armor by exactly 1.75");
        h.succeed();
    }

    @GameTest(template = "empty", timeoutTicks = 80)
    public static void g1WeakPointClosesAndBerserkStartsAt30Percent(GameTestHelper h) {
        var birkin = h.spawn(ModEntities.G1_BIRKIN.get(), new BlockPos(4, 1, 4));
        birkin.setNoAi(true);
        birkin.openWeakPoint(10);
        h.runAfterDelay(12, () -> {
            h.assertTrue(!birkin.isEyeOpen(), "Weak point must not stay open forever");
            birkin.setHealth(145);
            birkin.updatePhase();
            h.assertTrue(!birkin.isBerserk(), "Berserk must not start above 30 percent");
            birkin.setHealth(144);
            birkin.updatePhase();
            h.assertTrue(birkin.isBerserk() && birkin.isEyeOpen(), "30 percent phase must open the eye");
            h.succeed();
        });
    }

    @GameTest(template = "empty", timeoutTicks = 40)
    public static void reloadClearsTransientCombatState(GameTestHelper h) {
        var source = h.spawn(ModEntities.G1_BIRKIN.get(), new BlockPos(4, 1, 4));
        source.openWeakPoint(100);
        CompoundTag saved = new CompoundTag();
        source.saveWithoutId(saved);
        var loaded = ModEntities.G1_BIRKIN.get().create(h.getLevel());
        h.assertTrue(loaded != null, "Entity must load on dedicated server");
        loaded.load(saved);
        h.assertTrue(!loaded.isEyeOpen() && !loaded.attacking(), "Reload must not retain stuck hit windows");
        loaded.discard();
        h.succeed();
    }

    @GameTest(template = "empty", timeoutTicks = 100)
    public static void oddAndEvenBossesPursueFromTwelveBlocks(GameTestHelper h) {
        for (int x = 0; x < 16; x++) for (int z = 0; z < 16; z++) {
            h.getLevel().setBlockAndUpdate(h.absolutePos(new BlockPos(x, 0, z)), Blocks.STONE.defaultBlockState());
        }
        EncounterMob[] bosses = {
            spawnParity(h, ModEntities.TYRANT.get(), new BlockPos(1, 1, 2), 0),
            spawnParity(h, ModEntities.TYRANT.get(), new BlockPos(1, 1, 5), 1),
            spawnParity(h, ModEntities.G1_BIRKIN.get(), new BlockPos(1, 1, 8), 0),
            spawnParity(h, ModEntities.G1_BIRKIN.get(), new BlockPos(1, 1, 11), 1)
        };
        var targets = new net.minecraft.world.entity.animal.IronGolem[bosses.length];
        double[] initialDistance = new double[bosses.length];
        for (int i = 0; i < bosses.length; i++) {
            var target = h.spawn(EntityType.IRON_GOLEM, new BlockPos(14, 1, 2 + i * 3));
            target.setNoAi(true);
            targets[i] = target;
            bosses[i].setTarget(target);
            initialDistance[i] = bosses[i].distanceTo(target);
            h.assertTrue(initialDistance[i] >= 12, "Pursuit fixture must start outside attack range");
        }
        h.runAfterDelay(50, () -> {
            for (int i = 0; i < bosses.length; i++) {
                h.assertTrue(bosses[i].distanceTo(targets[i]) < initialDistance[i] - 2, "Boss must pursue for both ID parities: " + bosses[i].assetId() + " id=" + bosses[i].getId());
            }
            h.succeed();
        });
    }

    private static <T extends EncounterMob> T spawnParity(GameTestHelper h, EntityType<T> type, BlockPos relative, int parity) {
        for (int attempt = 0; attempt < 4; attempt++) {
            T mob = type.create(h.getLevel());
            if (mob != null && (mob.getId() & 1) == parity) {
                mob.moveTo(Vec3.atBottomCenterOf(h.absolutePos(relative)));
                h.getLevel().addFreshEntity(mob);
                return mob;
            }
            if (mob != null) mob.discard();
            if (attempt % 2 == 1) {
                var unused = EntityType.ARMOR_STAND.create(h.getLevel());
                if (unused != null) unused.discard();
            }
        }
        throw new IllegalStateException("Could not allocate the required entity ID parity");
    }

    @GameTest(template = "empty", timeoutTicks = 160)
    public static void lickerKeepsMeleeOnSilentTargetAfterSoundMemory(GameTestHelper h) {
        for (int x = 0; x < 16; x++) for (int z = 0; z < 16; z++) {
            h.getLevel().setBlockAndUpdate(h.absolutePos(new BlockPos(x, 0, z)), Blocks.STONE.defaultBlockState());
        }
        for (int x = 0; x < 16; x++) for (int y = 1; y <= 7; y++) {
            h.setBlock(new BlockPos(x, y, 8), Blocks.WHITE_CONCRETE);
        }
        var licker = h.spawn(ModEntities.LICKER.get(), new BlockPos(4, 1, 4));
        var target = h.spawn(EntityType.IRON_GOLEM, new BlockPos(6, 1, 4));
        target.setNoAi(true);
        target.getAttribute(Attributes.KNOCKBACK_RESISTANCE).setBaseValue(1);
        double startY = licker.getY();
        licker.hurt(licker.damageSources().mobAttack(target), 1);
        float original = target.getHealth();
        h.runAfterDelay(130, () -> {
            h.assertTrue(licker.getTarget() == target,
                    "Hurt aggro must survive 6s of silence while the Licker is still in claw range");
            h.assertTrue(original - target.getHealth() >= 5,
                    "Silent NoAI dummy in claw range must take at least 5 HP of real AI damage");
            h.assertTrue(licker.getY() < startY + 1.5,
                    "Licker must claw the dummy instead of spider-climbing its collision");
            h.succeed();
        });
    }

    @GameTest(template = "empty", timeoutTicks = 160)
    public static void threeSilentDummiesEachTakeFiveHp(GameTestHelper h) {
        for (int x = 0; x < 16; x++) for (int z = 0; z < 16; z++) {
            h.getLevel().setBlockAndUpdate(h.absolutePos(new BlockPos(x, 0, z)), Blocks.STONE.defaultBlockState());
        }
        EncounterMob[] attackers = {
            h.spawn(ModEntities.TYRANT.get(), new BlockPos(2, 1, 2)),
            h.spawn(ModEntities.G1_BIRKIN.get(), new BlockPos(2, 1, 7)),
            h.spawn(ModEntities.LICKER.get(), new BlockPos(2, 1, 12))
        };
        var dummies = new net.minecraft.world.entity.animal.IronGolem[attackers.length];
        float[] original = new float[attackers.length];
        double[] startY = new double[attackers.length];
        for (int i = 0; i < attackers.length; i++) {
            var dummy = h.spawn(EntityType.IRON_GOLEM, new BlockPos(4, 1, 2 + i * 5));
            dummy.setNoAi(true);
            dummy.getAttribute(Attributes.KNOCKBACK_RESISTANCE).setBaseValue(1);
            dummies[i] = dummy;
            original[i] = dummy.getHealth();
            startY[i] = attackers[i].getY();
            attackers[i].hurt(attackers[i].damageSources().mobAttack(dummy), 1);
        }
        h.runAfterDelay(130, () -> {
            for (int i = 0; i < attackers.length; i++) {
                h.assertTrue(original[i] - dummies[i].getHealth() >= 5,
                        attackers[i].assetId() + " must deal at least 5 HP to its own silent dummy");
                h.assertTrue(attackers[i].getY() < startY[i] + 1.5,
                        attackers[i].assetId() + " must not climb off its dummy");
            }
            h.assertTrue(attackers[2].getTarget() == dummies[2],
                    "Licker hurt aggro must still point at its silent dummy after sound memory");
            h.succeed();
        });
    }

    @GameTest(template = "empty", timeoutTicks = 50)
    public static void lethalHitClearsLickerTargetAndAttackImmediately(GameTestHelper h) {
        var licker = h.spawn(ModEntities.LICKER.get(), new BlockPos(4, 1, 4));
        var attacker = h.spawn(EntityType.IRON_GOLEM, new BlockPos(4, 1, 6));
        attacker.setNoAi(true);
        attacker.setNoGravity(true);
        licker.setNoGravity(true);
        licker.getAttribute(Attributes.MOVEMENT_SPEED).setBaseValue(0);
        licker.hear(attacker.position(), attacker, 16);
        licker.hear(attacker.position(), attacker, 16);
        h.runAfterDelay(3, () -> {
            h.assertTrue(licker.attacking(), "Fixture must be attacking before lethal damage");
            licker.hurt(licker.damageSources().mobAttack(attacker), 10000);
            h.assertTrue(!licker.isAlive() && licker.getTarget() == null && !licker.attacking(), "Lethal damage must clear target and animation in the same tick");
        });
        h.runAfterDelay(5, () -> {
            h.assertTrue(licker.getTarget() == null && !licker.attacking(), "Dead Licker must not reacquire its attacker");
            h.succeed();
        });
    }
}
