package com.zeropointsix.redemo.entity;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.mojang.logging.LogUtils;
import com.zeropointsix.redemo.ResidentEvilMod;
import com.zeropointsix.redemo.config.CommonConfig;
import com.zeropointsix.redemo.registry.ModEntities;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.List;
import net.minecraft.core.BlockPos;
import net.minecraft.gametest.framework.AfterBatch;
import net.minecraft.gametest.framework.BeforeBatch;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.Difficulty;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.animal.IronGolem;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.gametest.GameTestHolder;
import net.minecraftforge.gametest.PrefixGameTestTemplate;

@GameTestHolder(ResidentEvilMod.MOD_ID)
@PrefixGameTestTemplate(false)
public final class CombatBalanceGameTests {
    private static final String BATCH = "combat_balance";
    private static final int ROUND_LIMIT = 2000;
    private static final long[] SEEDS = {11, 29, 47, 83, 101, 131, 167, 191, 229, 257};
    private static Difficulty previousDifficulty;

    private CombatBalanceGameTests() { }

    @BeforeBatch(batch = BATCH)
    public static void normalDifficulty(ServerLevel level) {
        previousDifficulty = level.getDifficulty();
        level.getServer().setDifficulty(Difficulty.NORMAL, true);
    }

    @AfterBatch(batch = BATCH)
    public static void restoreDifficulty(ServerLevel level) {
        if (previousDifficulty != null) level.getServer().setDifficulty(previousDifficulty, true);
    }

    @GameTest(template = "combat_arena", batch = BATCH, timeoutTicks = 21000)
    public static void lickerVersusOneGolem(GameTestHelper h) { measure(h, ModEntities.LICKER.get(), 1); }

    @GameTest(template = "combat_arena", batch = BATCH, timeoutTicks = 21000)
    public static void birkinVersusTwoGolems(GameTestHelper h) { measure(h, ModEntities.G1_BIRKIN.get(), 2); }

    @GameTest(template = "combat_arena", batch = BATCH, timeoutTicks = 21000)
    public static void birkinVersusThreeGolems(GameTestHelper h) { measure(h, ModEntities.G1_BIRKIN.get(), 3); }

    @GameTest(template = "combat_arena", batch = BATCH, timeoutTicks = 21000)
    public static void tyrantVersusFiveGolems(GameTestHelper h) { measure(h, ModEntities.TYRANT.get(), 5); }

    private static void measure(GameTestHelper h, EntityType<? extends EncounterMob> type, int count) {
        int rounds = Math.max(1, Math.min(SEEDS.length, Integer.getInteger("re_demo.combatTrials", 1)));
        Trial[] active = {null};
        int[] wins = {0}, valid = {0};
        double[] threeGolemScore = {0};
        var sequence = h.startSequence();
        for (int i = 0; i < rounds; i++) {
            long seed = SEEDS[i];
            sequence.thenExecute(() -> active[0] = new Trial(h, type, count, seed))
                    .thenWaitUntil(() -> h.assertTrue(active[0].finished(), "Natural AI combat still running"))
                    .thenExecute(() -> {
                        Trial trial = active[0];
                        try {
                            trial.record();
                            if (trial.valid) valid[0]++;
                            if (trial.mob.isAlive() && trial.golems.stream().noneMatch(IronGolem::isAlive)) wins[0]++;
                            // A loss with one partly injured survivor is still a contested 2-3 golem fight.
                            threeGolemScore[0] += count - trial.golems.stream().mapToDouble(g -> Math.max(0, g.getHealth()) / g.getMaxHealth()).sum()
                                    + Math.max(0, trial.mob.getHealth()) / trial.mob.getMaxHealth();
                        } finally {
                            trial.mob.discard();
                            trial.golems.forEach(IronGolem::discard);
                        }
                    }).thenIdle(5);
        }
        sequence.thenExecute(() -> {
            h.assertTrue(valid[0] == rounds, "Every duel must finish on the unobstructed arena, without timeout");
            if (Boolean.getBoolean("re_demo.requireBalance")) {
                int required = count == 3 ? 0 : count == 1 ? (rounds + 1) / 2 : rounds;
                h.assertTrue(wins[0] >= required, "Combat win target: " + wins[0] + "/" + rounds + ", required=" + required);
                if (count == 3) {
                    double score = threeGolemScore[0] / rounds;
                    h.assertTrue(score >= 2 && score <= 3.35,
                            "G1 vs 3 must be contested (2-3.35 golem-equivalent remaining-health score), got " + score);
                }
            }
        }).thenSucceed();
    }

    private static final class Trial {
        private final GameTestHelper helper;
        private final EncounterMob mob;
        private final List<IronGolem> golems = new ArrayList<>();
        private final Vec3 center;
        private final long seed, start;
        private final int[] attacks = new int[8];
        private int lastSequence;
        private boolean valid = true;
        private String outcome = "running";

        private Trial(GameTestHelper h, EntityType<? extends EncounterMob> type, int count, long seed) {
            helper = h;
            h.assertTrue(Math.abs(CommonConfig.DAMAGE_SCALE.get() - 1) < 0.0001,
                    "Combat benchmark requires damageScale=1, not a modified server config");
            this.seed = seed;
            center = Vec3.atBottomCenterOf(h.absolutePos(new BlockPos(24, 1, 24)));
            h.assertTrue(h.getLevel().getBlockState(h.absolutePos(new BlockPos(24, 0, 24))).is(Blocks.STONE),
                    "Arena template must actually place its flat stone floor before combat");
            mob = h.spawn(type, new BlockPos(24, 1, 21));
            mob.getRandom().setSeed(seed);
            mob.setYRot(0);
            for (int i = 0; i < count; i++) {
                IronGolem golem = h.spawn(EntityType.IRON_GOLEM, new BlockPos(24 + (i - count / 2) * 2, 1, 26));
                golem.getRandom().setSeed(seed * 31 + i);
                golem.setTarget(mob);
                golems.add(golem);
            }
            IronGolem nearest = golems.get(count / 2);
            mob.setTarget(nearest);
            if (mob instanceof LickerEntity licker) {
                licker.hear(nearest.position(), nearest, 24);
                licker.hear(nearest.position(), nearest, 24);
            }
            start = h.getLevel().getGameTime();
        }

        private boolean finished() {
            if (mob.attackSequence() != lastSequence) {
                lastSequence = mob.attackSequence();
                if (mob.attack() > 0 && mob.attack() < attacks.length) attacks[mob.attack()]++;
            }
            if (escaped(mob.position()) || golems.stream().anyMatch(g -> escaped(g.position()))) {
                outcome = "escaped_arena";
                valid = false;
                return true;
            }
            if (!mob.isAlive() || golems.stream().noneMatch(IronGolem::isAlive)) {
                outcome = mob.isAlive() ? "mob" : "golems";
                return true;
            }
            if (helper.getLevel().getGameTime() - start >= ROUND_LIMIT) {
                outcome = "timeout";
                valid = false;
                return true;
            }
            return false;
        }

        private boolean escaped(Vec3 position) {
            return Math.abs(position.x - center.x) > 21 || Math.abs(position.z - center.z) > 21 || position.y < center.y - 0.5;
        }

        private void record() {
            JsonObject report = new JsonObject();
            report.addProperty("label", System.getProperty("re_demo.combatLabel", "unlabelled"));
            report.addProperty("mob", mob.assetId());
            report.addProperty("golems", golems.size());
            report.addProperty("seed", seed);
            report.addProperty("difficulty", helper.getLevel().getDifficulty().name());
            report.addProperty("arena", "48x48 stone, open, full AI, normal attributes, initial targets only");
            report.addProperty("winner", outcome);
            report.addProperty("valid", valid);
            report.addProperty("ticks", helper.getLevel().getGameTime() - start);
            report.addProperty("seconds", (helper.getLevel().getGameTime() - start) / 20.0);
            report.addProperty("mob_hp", Math.max(0, mob.getHealth()));
            report.addProperty("mob_max_hp", mob.getMaxHealth());
            report.addProperty("damage_scale", CommonConfig.DAMAGE_SCALE.get());
            report.addProperty("armor", mob.getAttributeValue(Attributes.ARMOR));
            report.addProperty("movement_speed", mob.getAttributeValue(Attributes.MOVEMENT_SPEED));
            report.addProperty("knockback_resistance", mob.getAttributeValue(Attributes.KNOCKBACK_RESISTANCE));
            JsonArray hp = new JsonArray(), skillCounts = new JsonArray();
            golems.forEach(g -> hp.add(Math.max(0, g.getHealth())));
            for (int value : attacks) skillCounts.add(value);
            report.add("golem_hp", hp);
            report.add("attack_counts_by_id", skillCounts);
            LogUtils.getLogger().info("RE_DEMO_COMBAT {}", report);
            try {
                Files.writeString(Path.of("combat-results.jsonl"), report + System.lineSeparator(),
                        StandardOpenOption.CREATE, StandardOpenOption.APPEND);
            } catch (IOException e) {
                throw new IllegalStateException("Cannot persist real combat evidence", e);
            }
        }
    }
}
