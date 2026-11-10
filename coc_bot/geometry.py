"""Pure geometry and arithmetic helpers: no screen capture, no input."""

import config


def interpolate_points(p1, p2, num_points):
    """Generate intermediate points between two coordinates for turbo deployment."""
    points = []
    for i in range(num_points):
        t = i / (num_points - 1) if num_points > 1 else 0
        x = p1[0] + (p2[0] - p1[0]) * t
        y = p1[1] + (p2[1] - p1[1]) * t
        points.append((x, y))
    return points


def find_building_clusters(buildings_with_types, max_distance=125):
    """
    Find clusters of buildings that are ALL close together (not chained).

    Uses COMPLETE LINKAGE: Every building in a cluster must be within max_distance
    of every other building in that cluster. This ensures spells can hit all buildings.

    Args:
        buildings_with_types: List of (x, y, confidence, building_type) tuples (top-left corners)
        max_distance: Maximum center-to-center distance between ANY two buildings in cluster (default: 125px)

    Returns:
        List of clusters, each cluster is a list of (x, y, confidence, building_type) tuples
    """
    if not buildings_with_types:
        return []

    def get_center(building):
        """Get center coordinates of a building using its actual template size."""
        x, y, _, building_type = building
        w, h = config.ACHIEVEMENT_BUILDING_SIZES.get(building_type, (70, 70))
        return (x + w // 2, y + h // 2)

    def distance_between(b1, b2):
        """Calculate center-to-center distance between two buildings."""
        c1 = get_center(b1)
        c2 = get_center(b2)
        return ((c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2) ** 0.5

    def all_within_distance(cluster, new_building):
        """Check if new_building is within max_distance of ALL buildings in cluster."""
        for existing in cluster:
            if distance_between(existing, new_building) > max_distance:
                return False
        return True

    # Find all pairs of buildings within max_distance
    clusters = []
    used = set()

    # Sort buildings by confidence (highest first) for better cluster seeds
    sorted_buildings = sorted(buildings_with_types, key=lambda b: b[2], reverse=True)

    for i, seed in enumerate(sorted_buildings):
        if i in used:
            continue

        # Start new cluster with this seed
        cluster = [seed]
        used.add(i)

        # Try to add other buildings that are within max_distance of ALL cluster members
        for j, candidate in enumerate(sorted_buildings):
            if j in used:
                continue

            if all_within_distance(cluster, candidate):
                cluster.append(candidate)
                used.add(j)

        clusters.append(cluster)

    # Sort clusters by size (largest first)
    clusters.sort(key=lambda c: len(c), reverse=True)

    return clusters


def get_cluster_center(cluster):
    """
    Calculate the center point of a cluster of buildings.

    Note: Detection coordinates are TOP-LEFT corners of bounding boxes.
    Uses actual template sizes for each building type for accurate centering.

    Args:
        cluster: List of (x, y, confidence, building_type) tuples (top-left corners)

    Returns:
        (center_x, center_y) tuple - the center point between all buildings
    """
    if not cluster:
        return None

    # Calculate center of each building using its actual template size
    centers = []
    for building in cluster:
        x, y, _, building_type = building
        w, h = config.ACHIEVEMENT_BUILDING_SIZES.get(building_type, (70, 70))
        centers.append((x + w // 2, y + h // 2))

    avg_x = sum(c[0] for c in centers) / len(centers)
    avg_y = sum(c[1] for c in centers) / len(centers)

    return (int(avg_x), int(avg_y))


def calculate_deployment_step(troop_count, coord_count):
    """
    Calculate optimal step size for even troop distribution across coordinates.

    Args:
        troop_count: Number of troops to deploy
        coord_count: Number of available deployment coordinates

    Returns:
        Step size (int) - how many coordinates to skip between deployments
    """
    if troop_count == 0 or coord_count == 0:
        return 1

    # Calculate raw step based on troop density
    raw_step = coord_count // troop_count

    # Clamp between 1 and 10 for balance of coverage vs speed
    # - step=1: use every coordinate (dense, slower)
    # - step=10: skip 10 coords each (sparse, faster)
    step = max(1, min(raw_step, 10))

    return step


def get_opposite_side(side):
    """Get the opposite side for camera movement"""
    opposite_map = {"left": "right", "right": "left", "up": "down", "down": "up"}
    return opposite_map.get(side, "right")  # Default to right if unknown


def get_lightning_spell_targets(air_defenses):
    """
    Get air defense positions for lightning spell targeting.
    Returns list of (x, y) coordinates sorted by priority (highest level first).
    """
    if not air_defenses:
        return []

    # Sort by level (highest first) and return positions
    sorted_defenses = sorted(air_defenses, key=lambda x: x[2], reverse=True)
    return [(x, y) for x, y, _, _ in sorted_defenses]


def get_air_defense_proximity_sorter(side):
    if side == "left":
        return lambda ad: ad[0]  # x coordinate, smaller is closer to left
    elif side == "right":
        return lambda ad: -ad[0]  # x coordinate, larger is closer to right
    elif side == "up":
        return lambda ad: ad[1]  # y coordinate, smaller is closer to top
    elif side == "down":
        return lambda ad: -ad[1]  # y coordinate, larger is closer to bottom
    else:
        return lambda ad: 0


def calculate_lightning_spells_needed(air_defense_level, lightning_damage):
    """
    Calculate how many lightning spells are needed to destroy an air defense.
    Returns the number of spells needed.
    """
    hp = config.AIR_DEFENSE_HP.get(air_defense_level, 1000)  # Default to 1000 if level not found
    spells_needed = (hp + lightning_damage - 1) // lightning_damage  # Ceiling division
    return max(1, spells_needed)  # Minimum 1 spell
