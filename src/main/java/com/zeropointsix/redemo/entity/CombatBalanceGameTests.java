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
import java.util.HashSet;
import java.util.IdentityHashMap;
import java.util.Map;
import java.util.Set;
import net.minecraft.core.BlockPos;
import net.minecraft.gametest.framework.AfterBatch;
import net.minecraft.gametest.framework.BeforeBatch;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.Difficulty;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.damagesource.DamageTypes;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.animal.IronGolem;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.gametest.GameTestHolder;
import net.minecraftforge.gametest.PrefixGameTestTemplate;

@GameTestHolder(ResidentEvilMod.MOD_ID)
@PrefixGameTestTemplate(false)
public final class CombatBalanceGameTests {
    private static final String BATCH = "combat_balance";
    private static final int ROUND_LIMIT = 2000;
    private static final int ARENA_CENTER = 64;
    private static final int ARENA_RADIUS = 60;
    private static final long[] SEEDS = {11, 29, 47, 83, 101, 131, 167, 191, 229, 257};
    private static Difficulty previousDifficulty;
    private static final Set<Long> FORCED_ARENA_CHUNKS = new HashSet<>();

    private CombatBalanceGameTests() { }

    @BeforeBatch(batch = BATCH)
    public static void normalDifficulty(ServerLevel level) {
        previousDifficulty = level.getDifficulty();
        level.getServer().setDifficulty(Difficulty.NORMAL, true);
    }

    @AfterBatch(batch = BATCH)
    public static void restoreDifficulty(ServerLevel level) {
        if (previousDifficulty != null) level.getServer().setDifficulty(previousDifficulty, true);
        int owned = FORCED_ARENA_CHUNKS.size();
        for (long packed : FORCED_ARENA_CHUNKS) {
            ChunkPos chunk = new ChunkPos(packed);
            level.setChunkForced(chunk.x, chunk.z, false);
        }
        boolean released = FORCED_ARENA_CHUNKS.stream().noneMatch(level.getForcedChunks()::contains);
        LogUtils.getLogger().info("RE_DEMO_ARENA_RELEASE owned={} released={} remaining_forced={}",
                owned, released, level.getForcedChunks().size());
        FORCED_ARENA_CHUNKS.clear();
        if (!released) throw new IllegalStateException("Combat arena chunk tickets must be released after the batch");
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
        // GameTest only forces chunks near the structure origin, not a large arena's center.
        // Keep the whole open floor active; never steer or teleport its combatants.
        ChunkPos first = new ChunkPos(h.absolutePos(new BlockPos(0, 1, 0)));
        ChunkPos last = new ChunkPos(h.absolutePos(new BlockPos(127, 1, 127)));
        for (int x = first.x; x <= last.x; x++) for (int z = first.z; z <= last.z; z++) {
            long packed = ChunkPos.asLong(x, z);
            if (!h.getLevel().getForcedChunks().contains(packed)) {
                h.getLevel().setChunkForced(x, z, true);
                FORCED_ARENA_CHUNKS.add(packed);
            }
        }
        LogUtils.getLogger().info("RE_DEMO_ARENA_FORCE mob={} golems={} owned_chunks={}", type, count, FORCED_ARENA_CHUNKS);
        h.assertTrue(Math.abs(CommonConfig.DAMAGE_SCALE.get() - 1) < 0.0001,
                "Combat benchmark requires damageScale=1, not a modified server config");
        h.assertTrue(h.getLevel().getBlockState(h.absolutePos(new BlockPos(ARENA_CENTER, 1, ARENA_CENTER))).is(Blocks.STONE),
                "Arena template must actually place its flat stone floor before combat");
        int rounds = Math.max(1, Math.min(SEEDS.length, Integer.getInteger("re_demo.combatTrials", 1)));
        Trial[] active = {null};
        int[] wins = {0}, valid = {0};
        double[] threeGolemScore = {0};
        var sequence = h.startSequence();
        sequence.thenWaitUntil(() -> {
            for (int x = first.x; x <= last.x; x++) for (int z = first.z; z <= last.z; z++) {
                h.assertTrue(h.getLevel().isPositionEntityTicking(new BlockPos(x * 16 + 8, 0, z * 16 + 8)),
                        "Every arena chunk must be entity-ticking before either side spawns: " + x + "," + z);
            }
        }).thenExecute(() -> prepareOpenArena(h));
        for (int i = 0; i < rounds; i++) {
            long seed = SEEDS[i];
            sequence.thenExecute(() -> {
                        clearArenaCombatants(h);
                        active[0] = new Trial(h, type, count, seed);
                    })
                    .thenWaitUntil(() -> h.assertTrue(active[0] != null && active[0].finished(), "Natural AI combat still running"))
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
                int required = count == 3 ? (rounds + 4) / 5 : count == 1 ? rounds / 2 + 1 : rounds;
                h.assertTrue(wins[0] >= required, "Combat win target: " + wins[0] + "/" + rounds + ", required=" + required);
                if (count == 1 && rounds >= 5) h.assertTrue(wins[0] * 5 <= rounds * 4,
                        "Licker vs 1 must remain near parity (at most 80% wins), got " + wins[0] + "/" + rounds);
                if (count == 3) {
                    double score = threeGolemScore[0] / rounds;
                    h.assertTrue(score >= 2 && score <= 3.2,
                            "G1 vs 3 must be contested (2-3.2 golem-equivalent remaining-health score), got " + score);
                    if (rounds >= 5) h.assertTrue(wins[0] * 5 <= rounds * 4,
                            "G1 vs 3 requires 20-80% wins, got " + wins[0] + "/" + rounds);
                }
            }
        }).thenSucceed();
    }

    private static void clearArenaCombatants(GameTestHelper h) {
        AABB bounds = new AABB(h.absolutePos(new BlockPos(0, -4, 0)),
                h.absolutePos(new BlockPos(128, 16, 128)));
        var leftovers = h.getLevel().getEntitiesOfClass(LivingEntity.class, bounds,
                entity -> entity instanceof EncounterMob || entity instanceof IronGolem);
        if (!leftovers.isEmpty()) LogUtils.getLogger().info("RE_DEMO_ARENA_CLEANUP ids={}",
                leftovers.stream().map(entity -> entity.getType() + "#" + entity.getId()).toList());
        leftovers.forEach(LivingEntity::discard);
    }

    private static void prepareOpenArena(GameTestHelper h) {
        // Finish chunk generation before clearing: newly generated neighbor features must
        // not refill the test volume after the template was initially placed.
        for (int x = 0; x < 128; x++) for (int z = 0; z < 128; z++) {
            prepareOpenColumn(h.getLevel(), h.absolutePos(new BlockPos(x, 1, z)));
        }
    }

    static void prepareOpenColumn(ServerLevel level, BlockPos floor) {
        // Clearing only the template height leaves generated fluids above it free
        // to fall into later rounds. Clear the actual column before any AI spawns.
        int top = Math.min(level.getMaxBuildHeight() - 1, Math.max(floor.getY() + 12,
                level.getHeight(Heightmap.Types.WORLD_SURFACE, floor.getX(), floor.getZ())));
        for (int y = floor.getY(); y <= top; y++) {
            BlockPos position = new BlockPos(floor.getX(), y, floor.getZ());
            var wanted = y == floor.getY() ? Blocks.STONE.defaultBlockState() : Blocks.AIR.defaultBlockState();
            if (level.getBlockState(position) != wanted) level.setBlock(position, wanted, 2);
        }
    }

    private static final class Trial {
        private final GameTestHelper helper;
        private final EncounterMob mob;
        private final List<IronGolem> golems = new ArrayList<>();
        private final Vec3 center;
        private final long seed, start;
        private final int[] attacks = new int[8];
        private final int[] damageEvents = new int[8];
        private final double[] damageByAttack = new double[8];
        private final float[] previousGolemHp;
        private final Map<LivingEntity, Double> peakHeights = new IdentityHashMap<>();
        private final JsonArray naturalFalls = new JsonArray();
        private int lastSequence;
        private int idleTicks, idleStreak, longestIdleStreak;
        private double maxDistanceFromCenter;
        private float previousMobHp;
        private String invalidReason = "";
        private boolean valid = true;
        private String outcome = "running";

        private Trial(GameTestHelper h, EntityType<? extends EncounterMob> type, int count, long seed) {
            helper = h;
            this.seed = seed;
            // Structure blocks place template y=0 at helper y=1, one block above their origin.
            center = Vec3.atBottomCenterOf(h.absolutePos(new BlockPos(ARENA_CENTER, 2, ARENA_CENTER)));
            mob = h.spawn(type, new BlockPos(ARENA_CENTER, 2, ARENA_CENTER - 3));
            mob.getRandom().setSeed(seed);
            mob.setYRot(0);
            for (int i = 0; i < count; i++) {
                IronGolem golem = h.spawn(EntityType.IRON_GOLEM, new BlockPos(ARENA_CENTER + (i - count / 2) * 2, 2, ARENA_CENTER + 2));
                golem.getRandom().setSeed(seed * 31 + i);
                golem.setTarget(mob);
                golems.add(golem);
            }
            previousGolemHp = new float[count];
            for (int i = 0; i < count; i++) previousGolemHp[i] = golems.get(i).getHealth();
            previousMobHp = mob.getHealth();
            if (h.getLevel().getBlockCollisions(mob, mob.getBoundingBox()).iterator().hasNext()
                    || golems.stream().anyMatch(g -> h.getLevel().getBlockCollisions(g, g.getBoundingBox()).iterator().hasNext())) {
                valid = false;
                outcome = "obstructed_spawn";
                invalidReason = "A combatant spawned inside a block";
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
            if (!valid) return true;
            long elapsed = helper.getLevel().getGameTime() - start;
            if (elapsed >= 20 && (mob.tickCount < elapsed - 3
                    || golems.stream().anyMatch(g -> g.isAlive() && g.tickCount < elapsed - 3))) {
                outcome = "inactive_entities";
                valid = false;
                return true;
            }
            int attack = mob.attack() >= 0 && mob.attack() < damageEvents.length ? mob.attack() : 0;
            peakHeights.merge(mob, mob.getY() - center.y, Math::max);
            for (IronGolem golem : golems) peakHeights.merge(golem, golem.getY() - center.y, Math::max);
            if (mob.getHealth() < previousMobHp) {
                var source = mob.getLastDamageSource();
                if ((source == null || !golems.contains(source.getEntity()))
                        && !naturalCombatFall(mob, source, previousMobHp - mob.getHealth())) {
                    outcome = "environmental_damage";
                    invalidReason = "Mob hurt by " + (source == null ? "unknown" : source.getMsgId());
                    valid = false;
                    return true;
                }
            }
            previousMobHp = mob.getHealth();
            for (int i = 0; i < golems.size(); i++) {
                float health = Math.max(0, golems.get(i).getHealth());
                float damage = previousGolemHp[i] - health;
                if (damage > 0) {
                    var source = golems.get(i).getLastDamageSource();
                    if ((source == null || source.getEntity() != mob)
                            && !naturalCombatFall(golems.get(i), source, damage)) {
                        outcome = "environmental_damage";
                        invalidReason = "Golem hurt by " + (source == null ? "unknown" : source.getMsgId());
                        valid = false;
                        return true;
                    }
                    if (source != null && source.getEntity() == mob) {
                        damageEvents[attack]++;
                        damageByAttack[attack] += damage;
                    }
                }
                previousGolemHp[i] = health;
            }
            boolean idleInReach = !mob.attacking() && EncounterMob.validTarget(mob.getTarget())
                    && mob.distanceTo(mob.getTarget()) <= 4.2 && mob.hasLineOfSight(mob.getTarget());
            idleStreak = idleInReach ? idleStreak + 1 : 0;
            if (idleInReach) idleTicks++;
            longestIdleStreak = Math.max(longestIdleStreak, idleStreak);
            maxDistanceFromCenter = Math.max(maxDistanceFromCenter, mob.position().subtract(center).horizontalDistance());
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
            // No walls, teleports or inward steering: leave ample room for natural knockback.
            return Math.abs(position.x - center.x) > ARENA_RADIUS || Math.abs(position.z - center.z) > ARENA_RADIUS || position.y < center.y - 0.5;
        }

        private boolean naturalCombatFall(LivingEntity victim, DamageSource source, float damage) {
            if (source == null || !source.is(DamageTypes.FALL) || escaped(victim.position())) return false;
            LivingEntity attacker = victim.getLastHurtByMob();
            int sinceHit = victim.tickCount - victim.getLastHurtByMobTimestamp();
            boolean opponent = victim == mob ? golems.contains(attacker) : attacker == mob;
            double peak = peakHeights.getOrDefault(victim, 0.0);
            if (!opponent || sinceHit < 0 || sinceHit > 100 || peak <= 1
                    || Math.abs(victim.getY() - center.y) > 0.05
                    || !helper.getLevel().getBlockState(victim.blockPosition().below()).is(Blocks.STONE)) return false;
            // Golem uppercuts and G1 throws may naturally cause a fall onto the flat floor.
            // Record that physics damage separately; suffocation and other terrain damage stay invalid.
            JsonObject fall = new JsonObject();
            fall.addProperty("entity_id", victim.getId());
            fall.addProperty("tick", helper.getLevel().getGameTime() - start);
            fall.addProperty("damage", damage);
            fall.addProperty("peak_height", peak);
            fall.addProperty("ticks_since_opponent_hit", sinceHit);
            naturalFalls.add(fall);
            peakHeights.put(victim, 0.0);
            return true;
        }

        private void record() {
            JsonObject report = new JsonObject();
            report.addProperty("label", System.getProperty("re_demo.combatLabel", "unlabelled"));
            report.addProperty("mob", mob.assetId());
            report.addProperty("golems", golems.size());
            report.addProperty("seed", seed);
            report.addProperty("difficulty", helper.getLevel().getDifficulty().name());
            report.addProperty("arena", "128x128 stone, open, full AI, normal attributes, initial targets only");
            report.addProperty("world_seed", helper.getLevel().getSeed());
            report.addProperty("start_game_time", start);
            report.addProperty("mob_entity_id", mob.getId());
            report.addProperty("arena_center", center.toString());
            report.addProperty("idle_in_reach_ticks", idleTicks);
            report.addProperty("longest_idle_in_reach_ticks", longestIdleStreak);
            report.addProperty("max_distance_from_center", maxDistanceFromCenter);
            report.addProperty("winner", outcome);
            report.addProperty("valid", valid);
            report.addProperty("invalid_reason", invalidReason);
            report.add("natural_combat_falls", naturalFalls);
            report.addProperty("ticks", helper.getLevel().getGameTime() - start);
            report.addProperty("seconds", (helper.getLevel().getGameTime() - start) / 20.0);
            report.addProperty("mob_hp", Math.max(0, mob.getHealth()));
            report.addProperty("mob_max_hp", mob.getMaxHealth());
            report.addProperty("damage_scale", CommonConfig.DAMAGE_SCALE.get());
            report.addProperty("armor", mob.getAttributeValue(Attributes.ARMOR));
            report.addProperty("movement_speed", mob.getAttributeValue(Attributes.MOVEMENT_SPEED));
            report.addProperty("knockback_resistance", mob.getAttributeValue(Attributes.KNOCKBACK_RESISTANCE));
            JsonArray hp = new JsonArray(), skillCounts = new JsonArray(), hits = new JsonArray(), damage = new JsonArray();
            golems.forEach(g -> hp.add(Math.max(0, g.getHealth())));
            for (int value : attacks) skillCounts.add(value);
            for (int value : damageEvents) hits.add(value);
            for (double value : damageByAttack) damage.add(value);
            report.add("golem_hp", hp);
            report.add("attack_counts_by_id", skillCounts);
            report.add("observed_damage_events_by_attack_id", hits);
            report.add("observed_damage_by_attack_id", damage);
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
