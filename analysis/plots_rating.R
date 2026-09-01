# ============================================================
# Script:      plots_rating.R
#
# Purpose:
#   Processes personality ratings collected across multiple methods
#   (Self-report, Others-report, AI ad hoc, and other AI ratings)
#   and conditions (Open vs. Structured interviews), then generates
#   distribution, descriptive, and convergent-validity (MTMM) plots
#   at both the facet and dimension level.
#
# Workflow:
#   1. Data wrangling
#      - Loads merged participant data and per-method rating files.
#      - Reverse-codes inverted items, computes facet and dimension
#        scores, and sets facets missing from incomplete interviews
#        to NaN.
#      - Combines all methods into long-format data frames
#        (facets_long, dimensions_long) with condition_group labels
#        ("Open" vs. "Structured").
#
#   2. Distribution plots
#      - Density plots of scores by facet/dimension, split by
#        condition and by method.
#
#   3. Descriptive statistics plots
#      - Bar plots of Mean, SD, Skewness, and Kurtosis per facet/
#        dimension, method, and condition group.
#
#   4. Convergent validity (MTMM) plots
#      - Monotrait-heteromethod correlations: each method's scores
#        correlated against a reference method (Self-report or
#        Others-report), separately per facet/dimension and
#        condition group, with analytic (Fisher-z) SE whiskers.
#
# Inputs:
#   - data/df_merged_cleaned.csv        Merged, cleaned participant data
#   - results/ratings/*.csv             Per-method AI rating files
#
# Outputs (written to figures/):
#   - rating_distributions/             Density plots
#   - rating_descriptives/              Descriptive statistic bar plots
#   - rating_convergence/               MTMM convergent validity plots
#
# Dependencies:
#   tidyverse, ggplot2, colorspace, purrr, psych, stringr,
#   patchwork, ggh4x, RColorBrewer
#
# Notes:
#   - Set working directory to the script's source file location
#     before running (uses relative paths for data/figures).
#   - Plot dimensions and color palette are configured in the
#     Config section (PLOTS_WIDTH/HEIGHT, BREWER_PALETTE).
# ============================================================

library(tidyverse)
library(ggplot2)
library(colorspace)
library(purrr)
library(psych)
library(stringr)
library(patchwork)
library(ggh4x)
library(RColorBrewer)

# ============================================================
# Config
# ============================================================

# --- Note: Set working directory to source file location

# Inputs
DATA_DIR = "data/"
RATINGS_DIR = "results/ratings/"

# Outputs
FIGURES_DIR = "figures/"

# Color scheme
BREWER_PALETTE = "Set2"

# Plot format
W_H_RATIO <- 10.5 / 9
PLOTS_HEIGHT <- 29.7
PLOTS_WIDTH  <- PLOTS_HEIGHT * W_H_RATIO
DPI = 300

# ============================================================
# Data wrangling
# ============================================================

# Load data
df <- read.csv(paste0(DATA_DIR, "df_merged_cleaned.csv"))

rating_files <- list.files(RATINGS_DIR)
rating_dfs <- list()

for(file in rating_files){
  rating_dfs[[gsub(".csv", "", file)]] <- read.csv(paste0(RATINGS_DIR, file))
}

# Add selbstbericht, fremdbericht and ad_hoc_ai_rating to rating_dfs
rating_dfs$selbstbericht <- df %>% select(participant_id, selbst_x42i02_a_co080:selbst_hex_oe_u_r_04)
names(rating_dfs$selbstbericht) <- sub("^selbst_", "", names(rating_dfs$selbstbericht))
rating_dfs$selbstbericht$label <- "selbstbericht"

rating_dfs$fremdbericht <- df %>% select(participant_id, fremd_x42i29_a_fr066:fremd_x42i51_hh_mo008)
names(rating_dfs$fremdbericht) <- sub("^fremd_", "", names(rating_dfs$fremdbericht))
rating_dfs$fremdbericht$label <- "fremdbericht"

rating_dfs$ai_ad_hoc <- df %>% select(participant_id, ai_assessment_A.Fr: ai_assessment_HH.Mo)
rating_dfs$ai_ad_hoc <- rating_dfs$ai_ad_hoc %>%
  rename_with(
    ~ tolower(gsub("\\.", "_", sub("^ai_assessment_", "", .x))),
    starts_with("ai_assessment_")
  )
rating_dfs$ai_ad_hoc$label <- "ai_ad_hoc"

# Data wrangling rating_dfs

## Add condition, completeness_missing_facets and completeness_items
for(i in seq_along(rating_dfs)) {
  rating_dfs[[i]] <- left_join(
    rating_dfs[[i]],
    df[, c("participant_id", "condition", "completeness_missing_facets", "completeness_items")],
    by = "participant_id"
  )
}

## Set x42i14_a_fr084 (second item in interview) to NA if completeness_items == "nein"
for(i in seq_along(rating_dfs)){
  if("x42i14_a_fr084" %in% colnames(rating_dfs[[i]])){
    rating_dfs[[i]]$x42i14_a_fr084[rating_dfs[[i]]$completeness_items == "nein"] <- NA
  }
}

## Recode inverted items (selbstbericht is already inverted)
reverse_coded_items <- c("x42i23_e_sb010",
                         "x42i10_e_sb014",
                         "x42i22_e_sb026",
                         
                         "x42i47_hh_si001",
                         "x42i04_hh_si009",
                         
                         "x42i31_hh_fa006",
                         "x42i08_hh_fa002",
                         
                         "x42i24_hh_mo016")

for(i in seq_along(rating_dfs)){
  if(any(reverse_coded_items %in% names(rating_dfs[[i]])) & names(rating_dfs)[i] != "selbstbericht"){
    for(item in reverse_coded_items){
      if(item %in% names(rating_dfs[[i]])){
        rating_dfs[[i]][[item]] <- 6 - rating_dfs[[i]][[item]]
        names(rating_dfs[[i]])[names(rating_dfs[[i]]) == item] <- paste0(item, "_r")
      }
    }
  }
}

# Calculate facet scores
for(i in seq_along(rating_dfs)){
  if(names(rating_dfs)[i] == "selbstbericht"){
    facet_names <- c("a_fr", "a_co", "a_h", "c_hw", "c_o", "e_a", "e_sb", "e_so", "n_d",
                     "n_ir", "n_st", "o_in", "o_r", "o_sc", "hh_si", "hh_f", "hh_m")
    
    for(facet in facet_names) {
      item_cols <- grep(paste0(
        "(?:_", facet, "_?[0-9]+_?r?$|",
        "_", facet, "_r_[0-9]+$)"
      ),
      names(rating_dfs[[i]]), value = TRUE)
      rating_dfs[[i]][[facet]] <- rowMeans(rating_dfs[[i]][, item_cols, drop = FALSE], na.rm = TRUE)
    }
    
    rating_dfs[[i]] <- rating_dfs[[i]] %>%
      rename(
        hh_fa = hh_f,
        hh_mo = hh_m
      )
  } else if(any(grepl("x42i", names(rating_dfs[[i]])))){
    facet_names <- c("a_fr", "a_co", "a_h", "c_hw", "c_o", "e_a", "e_sb", "e_so", "n_d",
                     "n_ir", "n_st", "o_in", "o_r", "o_sc", "hh_si", "hh_fa", "hh_mo")
    
    for(facet in facet_names){
      item_cols <- grep(paste0("_", facet, "[0-9]+_?r?$"), names(rating_dfs[[i]]), value = TRUE)
      rating_dfs[[i]][[facet]] <- rowMeans(rating_dfs[[i]][, item_cols, drop = FALSE], na.rm = TRUE)
    }
  }
}

# Set facet_scores of facets not talked about in the interview to NA
facet_names <- c("a_fr", "a_co", "a_h", "c_hw", "c_o", "e_a", "e_sb", "e_so", "n_d",
                 "n_ir", "n_st", "o_in", "o_r", "o_sc", "hh_si", "hh_fa", "hh_mo")

rating_dfs <- lapply(rating_dfs, function(rating_df) {
  
  for (i in seq_len(nrow(rating_df))){
    missing_facets <- unlist(strsplit(
      gsub("\\[|\\]|'", "", rating_df$completeness_missing_facets[i]),
      ","
    ))
    
    missing_facets <- trimws(missing_facets)
    
    missing_cols <- intersect(
      gsub("-", "_", tolower(missing_facets)),
      facet_names
    )
    
    rating_df[i, missing_cols] <- NaN
  }
  
  rating_df
})

# Calculate dimension scores
dimension_names <- c("a", "c", "e", "n", "o", "hh")
for(i in seq_along(rating_dfs)){
  for(dimension in dimension_names){
    facet_cols <- grep(paste0(dimension, "_", "[a-z]+"), names(rating_dfs[[i]]), value = TRUE)
    rating_dfs[[i]][[dimension]] <- rowMeans(rating_dfs[[i]][, facet_cols, drop = FALSE], na.rm = TRUE)
  }
}

# ============================================================
# Build analysis dfs and label lists
# ============================================================

# Label lists
facet_names <- c(
  "a_fr", "a_co", "a_h",
  "c_hw", "c_o",
  "e_a", "e_sb", "e_so",
  "n_d", "n_ir", "n_st",
  "o_in", "o_r", "o_sc",
  "hh_si", "hh_fa", "hh_mo"
)

facet_labels <- c(
  a_fr  = "A Friendly",
  a_co  = "A Considerate",
  a_h   = "A Helpful",
  
  c_hw  = "C Hard Working",
  c_o   = "C Organized",
  
  e_a   = "E Assertive",
  e_sb  = "E Self-confident",
  e_so  = "E Socially Active",
  
  n_d   = "N Depressed",
  n_ir  = "N Irritable",
  n_st  = "N Nervous",
  
  o_in  = "O Intellectual",
  o_r   = "O Reflective",
  o_sc  = "O Scientific Interest",
  
  hh_si = "HH Sincerity",
  hh_fa = "HH Fairness",
  hh_mo = "HH Modesty"
)

dimension_names <- c(
  "a", "c", "e", "n", "o", "hh"
)

dimension_labels <- c(
  a = "Agreeableness",
  c = "Conscientiousness",
  e = "Extraversion",
  n = "Neuroticism",
  o = "Openness",
  hh = "Honesty-Humility"
)

# Set displaying order
rating_order_end <- c("ai_ad_hoc", "fremdbericht", "selbstbericht")
rating_order <- setdiff(names(rating_dfs), rating_order_end)
rating_order <- c(rating_order, rating_order_end)

rating_labels <- c()
for(rating in setdiff(rating_order, rating_order_end)){
  parts <- str_split(rating, "_", simplify = TRUE)
  rating_labels[rating] <- paste0(
    str_to_sentence(parts[1]), "\n",
    paste(str_to_title(parts[-1]), collapse = " × ")
  )
}
rating_labels <- c(
  rating_labels,
  ai_ad_hoc = "AI ad hoc",
  fremdbericht = "Others-report",
  selbstbericht = "Self-report"
)

# Combine dfs
rating_all <- rating_dfs %>%
  imap_dfr(~ .x) %>%
  select( # select only necessary variables
    label,
    participant_id,
    condition,
    all_of(facet_names),
    all_of(dimension_names)
  )

# Add condition_group variable
rating_all <- rating_all %>%
  mutate(
    condition_group = case_when(
      condition %in% c(
        "structured-write",
        "structured-speech"
      ) ~ "Structured",
      
      condition %in% c(
        "open-write",
        "open-speech"
      ) ~ "Open",
      
      TRUE ~ NA_character_
    )
  )

# Convert to long format

## facets
facets_long <- rating_all %>%
  select(
    label,
    participant_id,
    condition,
    condition_group,
    all_of(facet_names)
  ) %>%
  pivot_longer(
    cols = all_of(facet_names),
    names_to = "facet",
    values_to = "score"
  ) %>%
  mutate(
    facet = factor(
      facet,
      levels = facet_names,
      labels = facet_labels
    ),
    label = factor(
      label,
      levels = rating_order,
      labels = rating_labels
    )
  )

## dimensions
dimensions_long <- rating_all %>%
  select(
    label,
    participant_id,
    condition,
    condition_group,
    all_of(dimension_names)
  ) %>%
  pivot_longer(
    cols = all_of(dimension_names),
    names_to = "dimension",
    values_to = "score"
  ) %>%
  mutate(
    dimension = factor(
      dimension,
      levels = dimension_names,
      labels = dimension_labels
    ),
    label = factor(
      label,
      levels = rating_order,
      labels = rating_labels
    )
  )

# Ns
n_ratings <- list()

## facets
n_ratings[["facets_conditions"]] <- facets_long %>%
  group_by(label, condition, facet) %>%
  summarise(
    N = n_distinct(participant_id[!is.na(score)]),
    .groups = "drop"
  )

n_ratings[["facets_conditiongroups"]] <- facets_long %>%
  group_by(label, condition_group, facet) %>%
  summarise(
    N = n_distinct(participant_id[!is.na(score)]),
    .groups = "drop"
  )

# dimensions
n_ratings[["dimensions_conditions"]] <- dimensions_long %>%
  group_by(label, condition, dimension) %>%
  summarise(
    N = n_distinct(participant_id[!is.na(score)]),
    .groups = "drop"
  )

n_ratings[["dimensions_conditiongroups"]] <- dimensions_long %>%
  group_by(label, condition_group, dimension) %>%
  summarise(
    N = n_distinct(participant_id[!is.na(score)]),
    .groups = "drop"
  )

# ============================================================
# Generate plots
# ============================================================

# Distribution plots -----------------------------------------
plots_distributions <- list()

## Facets, ratings x condition
note_message <- n_ratings[["facets_conditions"]] %>%
  group_by(condition) %>%
  summarise(
    N_min = min(N),
    N_max = max(N),
    .groups = "drop"
  ) %>%
  mutate(
    text = paste0(
      condition, " = [", N_min, "; ", N_max, "]" )
  ) %>%
  summarise(
    text = paste(text, collapse = ", ")
  ) %>%
  pull(text)
  
plots_distributions[["distributions_facets_ratings_condition"]] <- ggplot(
  facets_long,
  aes(
    x = score,
    fill = condition,
    colour = condition
  )) +
  geom_density(
    alpha = 0.25,
    linewidth = 0.5,
    na.rm = TRUE
  ) +
  facet_grid(
    label ~ facet,
    scales = "free_y",
    switch = "x"
  ) +
  labs(
    title = "Distribution of Scores Across Conditions",
    subtitle = paste0(
      "Density plots for facet x rating\n",
      "N ranges across the 17 facets: ",
      note_message
    ),
    x = NULL,
    y = NULL,
    fill = "Condition",
    colour = "Condition"
  ) +
  theme_minimal(base_size = 11) +
  theme(
    axis.title.x = element_blank(),
    axis.text.x = element_blank(),
    axis.ticks.x = element_blank(),
    
    strip.placement = "outside",
    strip.text.x = element_text(
      angle = 67.5,
      hjust = 0.5,
      vjust = 0.75,
    ),
    strip.text.y = element_text(
      angle = 0,
      face = "bold",
      hjust = 0
    ),
    panel.grid.minor = element_blank(),
    legend.position = "bottom"
  )

## Dimensions, ratings x condition
note_message <- n_ratings[["dimensions_conditions"]] %>%
  group_by(condition) %>%
  summarise(
    N_min = min(N),
    N_max = max(N),
    .groups = "drop"
  ) %>%
  mutate(
    text = paste0(
      condition, " = [", N_min, "; ", N_max, "]" )
  ) %>%
  summarise(
    text = paste(text, collapse = ", ")
  ) %>%
  pull(text)

plots_distributions[["distributions_dimensions_ratings_condition"]] <- ggplot(
  dimensions_long,
  aes(
    x = score,
    fill = condition,
    colour = condition
  )) +
  geom_density(
    alpha = 0.25,
    linewidth = 0.5,
    na.rm = TRUE
  ) +
  facet_grid(
    label ~ dimension,
    scales = "free_y",
    switch = "x"
  ) +
  labs(
    title = "Distribution of Scores Across Conditions",
    subtitle = paste0(
      "Density plots for dimensions x rating\n",
      "N ranges across the 6 dimensions: ",
      note_message
    ),
    x = NULL,
    y = NULL,
    fill = "Condition",
    colour = "Condition"
  ) +
  theme_minimal(base_size = 11) +
  theme(
    axis.title.x = element_blank(),
    axis.text.x = element_blank(),
    axis.ticks.x = element_blank(),
    
    strip.placement = "outside",
    strip.text.x = element_text(
      angle = 0,
      hjust = 0.5,
      vjust = 1
    ),
    strip.text.y = element_text(
      angle = 0,
      face = "bold",
      hjust = 0
    ),
    panel.grid.minor = element_blank(),
    legend.position = "bottom"
  )

## Facets, condition_groups x ratings
note_message <- n_ratings[["facets_conditiongroups"]] %>%
  group_by(condition_group) %>%
  summarise(
    N_min = min(N),
    N_max = max(N),
    .groups = "drop"
  ) %>%
  mutate(
    text = paste0(
      condition_group, " = [", N_min, "; ", N_max, "]" )
  ) %>%
  summarise(
    text = paste(text, collapse = ", ")
  ) %>%
  pull(text)

plots_distributions[["distributions_facets_conditiongroups_ratings"]] <- ggplot(
  facets_long,
  aes(
    x = score,
    fill = label,
    colour = label
  )) +
  geom_density(
    alpha = 0.25,
    linewidth = 0.5,
    na.rm = TRUE
  ) +
  facet_grid(
    condition_group ~ facet,
    scales = "free_y",
    switch = "both"
  ) +
  labs(
    title = "Distribution of Scores Across Condition Groups",
    subtitle = paste0(
      "Density plots for rating x facets\n",
      "N ranges across the 17 facets: ",
      note_message
    ),
    x = NULL,
    y = NULL,
    fill = "Rating",
    colour = "Rating"
  ) +
  theme_minimal(base_size = 11) +
  theme(
    axis.title.x = element_blank(),
    axis.text.x = element_blank(),
    axis.ticks.x = element_blank(),
    
    strip.placement = "outside",
    strip.text.x = element_text(
      angle = 67.5,
      hjust = 0.5,
      vjust = 0.75,
    ),
    strip.text.y = element_text(
      angle = 0,
      face = "bold",
      hjust = 0.5
    ),
    panel.grid.minor = element_blank(),
    legend.position = "bottom"
  )

## Dimensions, condition_groups x ratings
note_message <- n_ratings[["dimensions_conditiongroups"]] %>%
  group_by(condition_group) %>%
  summarise(
    N_min = min(N),
    N_max = max(N),
    .groups = "drop"
  ) %>%
  mutate(
    text = paste0(
      condition_group, " = [", N_min, "; ", N_max, "]" )
  ) %>%
  summarise(
    text = paste(text, collapse = ", ")
  ) %>%
  pull(text)

plots_distributions[["distributions_dimensions_conditiongroups_ratings"]] <- ggplot(
  dimensions_long,
  aes(
    x = score,
    fill = label,
    colour = label
  )) +
  geom_density(
    alpha = 0.25,
    linewidth = 0.5,
    na.rm = TRUE
  ) +
  facet_grid(
    condition_group ~ dimension,
    scales = "free_y",
    switch = "both"
  ) +
  labs(
    title = "Distribution of Scores Across Conditions",
    subtitle = paste0(
      "Density plots for rating x dimensions\n",
      "N ranges across the 6 dimensions: ",
      note_message
    ),
    x = NULL,
    y = NULL,
    fill = "Rating",
    colour = "Rating"
  ) +
  theme_minimal(base_size = 11) +
  theme(
    axis.title.x = element_blank(),
    axis.text.x = element_blank(),
    axis.ticks.x = element_blank(),
    
    strip.placement = "outside",
    strip.text.x = element_text(
      angle = 0,
      hjust = 0.5,
      vjust = 1
    ),
    strip.text.y = element_text(
      angle = 0,
      face = "bold",
      hjust = 0.5
    ),
    panel.grid.minor = element_blank(),
    legend.position = "bottom"
  )

# --- Save plots
save_path = paste0(FIGURES_DIR, "rating_distributions")

dir.create(
  save_path,
  recursive = TRUE,
  showWarnings = FALSE
)

for(plot in names(plots_distributions)){
  ggsave(
    filename = file.path(
      save_path,
      paste0(plot, ".png")
    ),
    plot = plots_distributions[[plot]],
    
    width = PLOTS_WIDTH,
    height = PLOTS_HEIGHT,
    units = "cm",
    dpi = DPI
    
  )
}

# Descriptives plots -----------------------------------------
plots_descriptives <- list()

## Facets, condition_groups x rating
facets_summary <- facets_long %>%
  group_by(label, condition_group, facet) %>%
  summarise(
    stats = list(
      describe(score, na.rm = TRUE)
    ),
    .groups = "drop"
  ) %>%
  unnest_wider(stats) %>%
  select(label, condition_group, facet, mean, sd, skew, kurtosis) %>%
  pivot_longer(
    cols = c(mean, sd, skew, kurtosis),
    names_to = "statistic",
    values_to = "value"
  ) %>%
  mutate(
    statistic = factor(
      statistic,
      levels = c("mean", "sd", "skew", "kurtosis"),
      labels = c("Mean", "SD", "Skewness", "Kurtosis")
    )
  )

note_message <- n_ratings[["facets_conditiongroups"]] %>%
  group_by(condition_group) %>%
  summarise(
    N_min = min(N),
    N_max = max(N),
    .groups = "drop"
  ) %>%
  mutate(
    text = paste0(
      condition_group, " = [", N_min, "; ", N_max, "]" )
  ) %>%
  summarise(
    text = paste(text, collapse = ", ")
  ) %>%
  pull(text)

make_block <- function(df, group_label, show_bottom_strip) {
  sub <- filter(df, condition_group == group_label)
  
  ggplot(
    sub,
    aes(
      x = label,
      y = value,
      fill = label
      )
    ) +
    geom_col(width = 0.9) +
    facet_nested(
      rows = vars(statistic),
      cols = vars(facet),
      scales = "free_y",
      switch = "both"
    ) +
    scale_fill_brewer(palette = BREWER_PALETTE) +
    labs(
      x = NULL,
      y = NULL,
      fill = "Label",
      title = group_label
    ) +
    theme_minimal(base_size = 11) +
    theme(
      legend.position = "none",
      axis.text.x = element_blank(),
      axis.ticks.x = element_blank(),
      strip.text.y = element_text(face = "bold"),
      strip.text.x = if (show_bottom_strip)
        element_text(
          angle = 67.5,
          hjust = 0.5,
          vjust = 0.75
        ) 
      else element_blank(),
      strip.placement = "outside",
      plot.title = element_text(
        face = "bold",
        hjust = 0,
        size = 11
      )
    )
}

p_open <- make_block(facets_summary, "Open", show_bottom_strip = FALSE)
p_structured <- make_block(facets_summary, "Structured", show_bottom_strip = TRUE)

plots_descriptives[["descriptives_facets_conditiongroups_ratings"]] <- p_open / p_structured +
  plot_layout(guides = "collect") +
  plot_annotation(
    title = "Facets Summary Statistics",
    subtitle = paste0(
      "Bar plots for statistic x facets\n",
      "N ranges across the 17 facets: ",
      note_message
    ),
    theme = theme(
      plot.title = element_text(
        face = "bold",
        size = 12,
        hjust = 0
      ),
      plot.subtitle = element_text(
        size = 11,
        hjust = 0
      )
    )
  ) &
  theme(legend.position = "bottom")

## Facets, condition_groups x rating
dimensions_summary <- dimensions_long %>%
  group_by(label, condition_group, dimension) %>%
  summarise(
    stats = list(
      describe(score, na.rm = TRUE)
    ),
    .groups = "drop"
  ) %>%
  unnest_wider(stats) %>%
  select(label, condition_group, dimension, mean, sd, skew, kurtosis) %>%
  pivot_longer(
    cols = c(mean, sd, skew, kurtosis),
    names_to = "statistic",
    values_to = "value"
  ) %>%
  mutate(
    statistic = factor(
      statistic,
      levels = c("mean", "sd", "skew", "kurtosis"),
      labels = c("Mean", "SD", "Skewness", "Kurtosis")
    )
  )

note_message <- n_ratings[["dimensions_conditiongroups"]] %>%
  group_by(condition_group) %>%
  summarise(
    N_min = min(N),
    N_max = max(N),
    .groups = "drop"
  ) %>%
  mutate(
    text = paste0(
      condition_group, " = [", N_min, "; ", N_max, "]" )
  ) %>%
  summarise(
    text = paste(text, collapse = ", ")
  ) %>%
  pull(text)

make_block <- function(df, group_label, show_bottom_strip) {
  sub <- filter(df, condition_group == group_label)
  
  ggplot(
    sub,
    aes(
      x = label,
      y = value,
      fill = label
    )
  ) +
    geom_col(width = 0.9) +
    facet_nested(
      rows = vars(statistic),
      cols = vars(dimension),
      scales = "free_y",
      switch = "both"
    ) +
    scale_fill_brewer(palette = BREWER_PALETTE) +
    labs(
      x = NULL,
      y = NULL,
      fill = "Label",
      title = group_label
    ) +
    theme_minimal(base_size = 11) +
    theme(
      legend.position = "none",
      axis.text.x = element_blank(),
      axis.ticks.x = element_blank(),
      strip.text.y = element_text(face = "bold"),
      strip.text.x = if (show_bottom_strip)
        element_text(
          angle = 0,
          hjust = 0.5,
          vjust = 0
        ) 
      else element_blank(),
      strip.placement = "outside",
      plot.title = element_text(
        face = "bold",
        hjust = 0,
        size = 11
      )
    )
}

p_open <- make_block(dimensions_summary, "Open", show_bottom_strip = FALSE)
p_structured <- make_block(dimensions_summary, "Structured", show_bottom_strip = TRUE)

plots_descriptives[["descriptives_dimensions_conditiongroups_ratings"]] <- p_open / p_structured +
  plot_layout(guides = "collect") +
  plot_annotation(
    title = "Dimensions Summary Statistics",
    subtitle = paste0(
      "Bar plots for statistic x dimensions\n",
      "N ranges across the 6 dimensions: ",
      note_message
    ),
    theme = theme(
      plot.title = element_text(
        face = "bold",
        size = 12,
        hjust = 0
      ),
      plot.subtitle = element_text(
        size = 11,
        hjust = 0
      )
    )
  ) &
  theme(legend.position = "bottom")

# --- Save plots
save_path = paste0(FIGURES_DIR, "rating_descriptives")

dir.create(
  save_path,
  recursive = TRUE,
  showWarnings = FALSE
)

for(plot in names(plots_descriptives)){
  ggsave(
    filename = file.path(
      save_path,
      paste0(plot, ".png")
    ),
    plot = plots_descriptives[[plot]],
    
    width = PLOTS_WIDTH,
    height = PLOTS_HEIGHT,
    units = "cm",
    dpi = DPI
    
  )
}

# Correlation plots ------------------------------------------
plots_convergence <- list()

## Facets, reference = Self-report
reference_label <- c(
  "Self-report" = "SR",
  "Others-report" = "OR"
)

ordered_labels <- c()
for(label in setdiff(rating_labels, names(reference_label))){
  ordered_labels[label] <- paste0(
    label, "\n- ", reference_label[1]
  )
}
ordered_labels[names(reference_label)[2]] = paste0(
  reference_label[2], "\n- ", reference_label[1]
)

# --- 1. Wide format: one row per participant x facet x condition_group,
#         columns = labels, so we can correlate label columns pairwise ---
wide_scores <- facets_long %>%
  select(participant_id, label, condition_group, facet, score) %>%
  pivot_wider(names_from = label, values_from = score)

# --- 2. Monotrait-heteromethod correlation: each label vs. reference,
#         same facet, same condition_group, across participants ---
get_mtmm_r <- function(df, ref) {
  map_dfr(names(ordered_labels), function(lab) {
    x <- df[[ref]]
    y <- df[[lab]]
    ok <- complete.cases(x, y)
    n <- sum(ok)
    
    if (n < 4) {
      return(tibble(label = lab, r = NA_real_, se = NA_real_, n = n))
    }
    
    r <- suppressWarnings(cor(x[ok], y[ok]))
    # Analytic SE via Fisher z, back-transformed to r-scale (delta method approx)
    z  <- atanh(r)
    se_z <- 1 / sqrt(n - 3)
    se_r <- se_z * (1 - r^2)   # delta-method approx SE on the r scale
    
    tibble(label = lab, r = r, se = se_r, n = n)
  })
}

mtmm_summary <- wide_scores %>%
  group_by(condition_group, facet) %>%
  group_modify(~ get_mtmm_r(.x, ref = names(reference_label)[1])) %>%
  ungroup() %>%
  mutate(
    label = factor(
      label,
      levels = names(ordered_labels),
      labels = unname(ordered_labels)
    )
  )

# --- 3. Set colors
base_colors <- brewer.pal(length(levels(mtmm_summary$label)), BREWER_PALETTE)
names(base_colors) <- levels(mtmm_summary$label)

or_label <- ordered_labels[[names(reference_label)[2]]]
base_colors[or_label] <- "grey60"

# --- 4. Plot: same structure as before, bars = r, whiskers = SE ---
make_block <- function(df, group_label, show_bottom_strip) {
  sub <- filter(df, condition_group == group_label)
  
  ggplot(
    sub,
    aes(
      x = label,
      y = r,
      fill = label
    )
  ) +
    geom_col(width = 0.9) +
    geom_errorbar(
      aes(ymin = r - se, ymax = r + se),
      width = 0.25, color = "black", linewidth = 0.4
    ) +
    facet_wrap(
      vars(facet),
      nrow = 1,
      strip.position = "bottom"
    ) +
    scale_fill_manual(values = base_colors) +
    labs(x = NULL, y = NULL, fill = "Label", title = group_label) +
    theme_minimal(base_size = 11) +
    theme(
      legend.position = "none",
      axis.text.x = element_blank(),
      axis.ticks.x = element_blank(),
      strip.text.x = if (show_bottom_strip)
        element_text(
          angle = 67.5,
          hjust = 0.5,
          vjust = 0.75
        )
      else element_blank(),
      strip.placement = "outside",
      plot.title = element_text(
        face = "bold",
        hjust = 0,
        size = 11)
    )
}

p_open <- make_block(mtmm_summary, "Open", show_bottom_strip = FALSE)
p_structured <- make_block(mtmm_summary, "Structured", show_bottom_strip = TRUE)

plots_convergence[["convergence_facets_self"]] <- p_open / p_structured +
  plot_layout(guides = "collect") +
  plot_annotation(
    title = paste0(
      "Convergent Validity: Monotrait-Heteromethod Correlations - Reference: ", names(reference_label)[1]
    ),
    subtitle = paste0(
      "Correlation of each method with ", names(reference_label)[1], " on the same facet, per condition.\n",
      "Error bars = analytic SE (Fisher-z / delta method)."
    ),
    theme = theme(
      plot.title = element_text(face = "bold", size = 12, hjust = 0),
      plot.subtitle = element_text(size = 11, hjust = 0)
    )
  ) &
  theme(legend.position = "bottom")

## Facets, reference = Others-report
reference_label <- c(
  "Others-report" = "OR",
  "Self-report" = "SR"
)

ordered_labels <- c()
for(label in setdiff(rating_labels, names(reference_label))){
  ordered_labels[label] <- paste0(
    label, "\n- ", reference_label[1]
  )
}
ordered_labels[names(reference_label)[2]] = paste0(
  reference_label[2], "\n- ", reference_label[1]
)

# --- 1. Wide format: one row per participant x facet x condition_group,
#         columns = labels, so we can correlate label columns pairwise ---
wide_scores <- facets_long %>%
  select(participant_id, label, condition_group, facet, score) %>%
  pivot_wider(names_from = label, values_from = score)

# --- 2. Monotrait-heteromethod correlation: each label vs. reference,
#         same facet, same condition_group, across participants ---
get_mtmm_r <- function(df, ref) {
  map_dfr(names(ordered_labels), function(lab) {
    x <- df[[ref]]
    y <- df[[lab]]
    ok <- complete.cases(x, y)
    n <- sum(ok)
    
    if (n < 4) {
      return(tibble(label = lab, r = NA_real_, se = NA_real_, n = n))
    }
    
    r <- suppressWarnings(cor(x[ok], y[ok]))
    # Analytic SE via Fisher z, back-transformed to r-scale (delta method approx)
    z  <- atanh(r)
    se_z <- 1 / sqrt(n - 3)
    se_r <- se_z * (1 - r^2)   # delta-method approx SE on the r scale
    
    tibble(label = lab, r = r, se = se_r, n = n)
  })
}

mtmm_summary <- wide_scores %>%
  group_by(condition_group, facet) %>%
  group_modify(~ get_mtmm_r(.x, ref = names(reference_label)[1])) %>%
  ungroup() %>%
  mutate(
    label = factor(
      label,
      levels = names(ordered_labels),
      labels = unname(ordered_labels)
    )
  )

# --- 3. Set colors
base_colors <- brewer.pal(length(levels(mtmm_summary$label)), BREWER_PALETTE)
names(base_colors) <- levels(mtmm_summary$label)

or_label <- ordered_labels[[names(reference_label)[2]]]
base_colors[or_label] <- "grey60"

# --- 4. Plot: same structure as before, bars = r, whiskers = SE ---
make_block <- function(df, group_label, show_bottom_strip) {
  sub <- filter(df, condition_group == group_label)
  
  ggplot(
    sub,
    aes(
      x = label,
      y = r,
      fill = label
    )
  ) +
    geom_col(width = 0.9) +
    geom_errorbar(
      aes(ymin = r - se, ymax = r + se),
      width = 0.25, color = "black", linewidth = 0.4
    ) +
    facet_wrap(
      vars(facet),
      nrow = 1,
      strip.position = "bottom"
    ) +
    scale_fill_manual(values = base_colors) +
    labs(x = NULL, y = NULL, fill = "Label", title = group_label) +
    theme_minimal(base_size = 11) +
    theme(
      legend.position = "none",
      axis.text.x = element_blank(),
      axis.ticks.x = element_blank(),
      strip.text.x = if (show_bottom_strip)
        element_text(
          angle = 67.5,
          hjust = 0.5,
          vjust = 0.75
        )
      else element_blank(),
      strip.placement = "outside",
      plot.title = element_text(
        face = "bold",
        hjust = 0,
        size = 11)
    )
}

p_open <- make_block(mtmm_summary, "Open", show_bottom_strip = FALSE)
p_structured <- make_block(mtmm_summary, "Structured", show_bottom_strip = TRUE)

plots_convergence[["convergence_facets_others"]] <- p_open / p_structured +
  plot_layout(guides = "collect") +
  plot_annotation(
    title = paste0(
      "Convergent Validity: Monotrait-Heteromethod Correlations - Reference: ", names(reference_label)[1]
    ),
    subtitle = paste0(
      "Correlation of each method with ", names(reference_label)[1], " on the same facet, per condition.\n",
      "Error bars = analytic SE (Fisher-z / delta method)."
    ),
    theme = theme(
      plot.title = element_text(face = "bold", size = 12, hjust = 0),
      plot.subtitle = element_text(size = 11, hjust = 0)
    )
  ) &
  theme(legend.position = "bottom")

## Dimensions, reference = Self-report
reference_label <- c(
  "Self-report" = "SR",
  "Others-report" = "OR"
)

ordered_labels <- c()
for(label in setdiff(rating_labels, names(reference_label))){
  ordered_labels[label] <- paste0(
    label, "\n- ", reference_label[1]
  )
}
ordered_labels[names(reference_label)[2]] = paste0(
  reference_label[2], "\n- ", reference_label[1]
)

# --- 1. Wide format: one row per participant x dimension x condition_group,
#         columns = labels, so we can correlate label columns pairwise ---
wide_scores <- dimensions_long %>%
  select(participant_id, label, condition_group, dimension, score) %>%
  pivot_wider(names_from = label, values_from = score)

# --- 2. Monotrait-heteromethod correlation: each label vs. reference,
#         same dimension, same condition_group, across participants ---
get_mtmm_r <- function(df, ref) {
  map_dfr(names(ordered_labels), function(lab) {
    x <- df[[ref]]
    y <- df[[lab]]
    ok <- complete.cases(x, y)
    n <- sum(ok)
    
    if (n < 4) {
      return(tibble(label = lab, r = NA_real_, se = NA_real_, n = n))
    }
    
    r <- suppressWarnings(cor(x[ok], y[ok]))
    # Analytic SE via Fisher z, back-transformed to r-scale (delta method approx)
    z  <- atanh(r)
    se_z <- 1 / sqrt(n - 3)
    se_r <- se_z * (1 - r^2)   # delta-method approx SE on the r scale
    
    tibble(label = lab, r = r, se = se_r, n = n)
  })
}

mtmm_summary <- wide_scores %>%
  group_by(condition_group, dimension) %>%
  group_modify(~ get_mtmm_r(.x, ref = names(reference_label)[1])) %>%
  ungroup() %>%
  mutate(
    label = factor(
      label,
      levels = names(ordered_labels),
      labels = unname(ordered_labels)
    )
  )

# --- 3. Set colors
base_colors <- brewer.pal(length(levels(mtmm_summary$label)), BREWER_PALETTE)
names(base_colors) <- levels(mtmm_summary$label)

or_label <- ordered_labels[[names(reference_label)[2]]]
base_colors[or_label] <- "grey60"

# --- 4. Plot: same structure as before, bars = r, whiskers = SE ---
make_block <- function(df, group_label, show_bottom_strip) {
  sub <- filter(df, condition_group == group_label)
  
  ggplot(
    sub,
    aes(
      x = label,
      y = r,
      fill = label
    )
  ) +
    geom_col(width = 0.9) +
    geom_errorbar(
      aes(ymin = r - se, ymax = r + se),
      width = 0.25, color = "black", linewidth = 0.4
    ) +
    facet_wrap(
      vars(dimension),
      nrow = 1,
      strip.position = "bottom"
    ) +
    scale_fill_manual(values = base_colors) +
    labs(x = NULL, y = NULL, fill = "Label", title = group_label) +
    theme_minimal(base_size = 11) +
    theme(
      legend.position = "none",
      axis.text.x = element_blank(),
      axis.ticks.x = element_blank(),
      strip.text.x = if (show_bottom_strip)
        element_text(
          angle = 0,
          hjust = 0.5,
          vjust = 0
        )
      else element_blank(),
      strip.placement = "outside",
      plot.title = element_text(
        face = "bold",
        hjust = 0,
        size = 11)
    )
}

p_open <- make_block(mtmm_summary, "Open", show_bottom_strip = FALSE)
p_structured <- make_block(mtmm_summary, "Structured", show_bottom_strip = TRUE)

plots_convergence[["convergence_dimensions_self"]] <- p_open / p_structured +
  plot_layout(guides = "collect") +
  plot_annotation(
    title = paste0(
      "Convergent Validity: Monotrait-Heteromethod Correlations - Reference: ", names(reference_label)[1]
    ),
    subtitle = paste0(
      "Correlation of each method with ", names(reference_label)[1], " on the same dimension, per condition.\n",
      "Error bars = analytic SE (Fisher-z / delta method)."
    ),
    theme = theme(
      plot.title = element_text(face = "bold", size = 12, hjust = 0),
      plot.subtitle = element_text(size = 11, hjust = 0)
    )
  ) &
  theme(legend.position = "bottom")

## Dimensions, reference = Others-report
reference_label <- c(
  "Others-report" = "OR",
  "Self-report" = "SR"
)

ordered_labels <- c()
for(label in setdiff(rating_labels, names(reference_label))){
  ordered_labels[label] <- paste0(
    label, "\n- ", reference_label[1]
  )
}
ordered_labels[names(reference_label)[2]] = paste0(
  reference_label[2], "\n- ", reference_label[1]
)

# --- 1. Wide format: one row per participant x dimension x condition_group,
#         columns = labels, so we can correlate label columns pairwise ---
wide_scores <- dimensions_long %>%
  select(participant_id, label, condition_group, dimension, score) %>%
  pivot_wider(names_from = label, values_from = score)

# --- 2. Monotrait-heteromethod correlation: each label vs. reference,
#         same dimension, same condition_group, across participants ---
get_mtmm_r <- function(df, ref) {
  map_dfr(names(ordered_labels), function(lab) {
    x <- df[[ref]]
    y <- df[[lab]]
    ok <- complete.cases(x, y)
    n <- sum(ok)
    
    if (n < 4) {
      return(tibble(label = lab, r = NA_real_, se = NA_real_, n = n))
    }
    
    r <- suppressWarnings(cor(x[ok], y[ok]))
    # Analytic SE via Fisher z, back-transformed to r-scale (delta method approx)
    z  <- atanh(r)
    se_z <- 1 / sqrt(n - 3)
    se_r <- se_z * (1 - r^2)   # delta-method approx SE on the r scale
    
    tibble(label = lab, r = r, se = se_r, n = n)
  })
}

mtmm_summary <- wide_scores %>%
  group_by(condition_group, dimension) %>%
  group_modify(~ get_mtmm_r(.x, ref = names(reference_label)[1])) %>%
  ungroup() %>%
  mutate(
    label = factor(
      label,
      levels = names(ordered_labels),
      labels = unname(ordered_labels)
    )
  )

# --- 3. Set colors
base_colors <- brewer.pal(length(levels(mtmm_summary$label)), BREWER_PALETTE)
names(base_colors) <- levels(mtmm_summary$label)

or_label <- ordered_labels[[names(reference_label)[2]]]
base_colors[or_label] <- "grey60"

# --- 4. Plot: same structure as before, bars = r, whiskers = SE ---
make_block <- function(df, group_label, show_bottom_strip) {
  sub <- filter(df, condition_group == group_label)
  
  ggplot(
    sub,
    aes(
      x = label,
      y = r,
      fill = label
    )
  ) +
    geom_col(width = 0.9) +
    geom_errorbar(
      aes(ymin = r - se, ymax = r + se),
      width = 0.25, color = "black", linewidth = 0.4
    ) +
    facet_wrap(
      vars(dimension),
      nrow = 1,
      strip.position = "bottom"
    ) +
    scale_fill_manual(values = base_colors) +
    labs(x = NULL, y = NULL, fill = "Label", title = group_label) +
    theme_minimal(base_size = 11) +
    theme(
      legend.position = "none",
      axis.text.x = element_blank(),
      axis.ticks.x = element_blank(),
      strip.text.x = if (show_bottom_strip)
        element_text(
          angle = 0,
          hjust = 0.5,
          vjust = 0
        )
      else element_blank(),
      strip.placement = "outside",
      plot.title = element_text(
        face = "bold",
        hjust = 0,
        size = 11)
    )
}

p_open <- make_block(mtmm_summary, "Open", show_bottom_strip = FALSE)
p_structured <- make_block(mtmm_summary, "Structured", show_bottom_strip = TRUE)

plots_convergence[["convergence_dimensions_others"]] <- p_open / p_structured +
  plot_layout(guides = "collect") +
  plot_annotation(
    title = paste0(
      "Convergent Validity: Monotrait-Heteromethod Correlations - Reference: ", names(reference_label)[1]
    ),
    subtitle = paste0(
      "Correlation of each method with ", names(reference_label)[1], " on the same dimension, per condition.\n",
      "Error bars = analytic SE (Fisher-z / delta method)."
    ),
    theme = theme(
      plot.title = element_text(face = "bold", size = 12, hjust = 0),
      plot.subtitle = element_text(size = 11, hjust = 0)
    )
  ) &
  theme(legend.position = "bottom")

# --- Save plots
save_path = paste0(FIGURES_DIR, "rating_convergence")

dir.create(
  save_path,
  recursive = TRUE,
  showWarnings = FALSE
)

for(plot in names(plots_convergence)){
  ggsave(
    filename = file.path(
      save_path,
      paste0(plot, ".png")
    ),
    plot = plots_convergence[[plot]],
    
    width = PLOTS_WIDTH,
    height = PLOTS_HEIGHT,
    units = "cm",
    dpi = DPI
    
  )
}