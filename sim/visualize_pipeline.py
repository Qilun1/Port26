from manim import *
import random
"""
Manim based script for visualizing the data flow from coarse weather data, 
through our AI engine, to fine weather output. 
The goal is to create a clear and engaging animation that highlights the transformation 
and improvement in resolution provided by our model.
"""


class PerfectlyAlignedWeatherFlow(Scene):
    def construct(self):
        random.seed(42)

        left_pos = LEFT * 4.5
        center_pos = ORIGIN
        right_pos = RIGHT * 4.5

        # ==========================================
        # STEP 1: Current 9km Weather
        # ==========================================
        # 3 squares x 1.2 width = 3.6 total width
        coarse_grid = VGroup(*[
            Square(side_length=1.2, fill_color=BLUE, fill_opacity=0.7, stroke_color=WHITE, stroke_width=2) 
            for _ in range(9)
        ]).arrange_in_grid(rows=3, cols=3, buff=0).move_to(left_pos)
        
        coarse_label = Text("Current Model: 9km", font_size=24).next_to(coarse_grid, UP, buff=0.4)
        
        self.play(Create(coarse_grid, lag_ratio=0.1), run_time=1.5)
        self.play(Write(coarse_label))
        self.wait(1)

        # ==========================================
        # STEP 1.5: Overlay MANY Sensors
        # ==========================================
        sensors = VGroup()
        for _ in range(40):
            x_offset = random.uniform(-1.7, 1.7)
            y_offset = random.uniform(-1.7, 1.7)
            dot = Dot(color=YELLOW, radius=0.06).move_to(coarse_grid.get_center() + RIGHT * x_offset + UP * y_offset)
            sensors.add(dot)

        sensor_label = Text("+ Dense Sensor Network", font_size=18, color=YELLOW).next_to(coarse_grid, DOWN, buff=0.3)

        self.play(Create(sensors, lag_ratio=0.05), Write(sensor_label), run_time=2)
        self.wait(1.5)

        # ==========================================
        # STEP 2: It Goes to the Model
        # ==========================================
        pinn_box = RoundedRectangle(corner_radius=0.2, height=2.5, width=2, color=PURPLE).move_to(center_pos)
        
        # REMOVED PINN MENTION, increased font size slightly
        pinn_label = Text("AI Engine", font_size=28).move_to(pinn_box.get_center())
        pinn_group = VGroup(pinn_box, pinn_label)
        
        self.play(FadeIn(pinn_group))

        arrow_in = Arrow(coarse_grid.get_right(), pinn_box.get_left(), buff=0.2)
        self.play(Create(arrow_in))
        
        self.play(Indicate(pinn_box, color=PURPLE_A, scale_factor=1.1, run_time=1.5))

        # ==========================================
        # STEP 3: Outputs Fine 30m Weather
        # ==========================================
        weather_colors = [BLUE_E, BLUE_D, BLUE_C, TEAL_E, TEAL_D, TEAL_C]
        
        # FIXED MATH: 12 squares x 0.3 width = 3.6 total width (Identical to coarse grid)
        fine_grid = VGroup(*[
            Square(side_length=0.3, fill_color=random.choice(weather_colors), fill_opacity=0.9, stroke_width=0.2) 
            for _ in range(144)
        ]).arrange_in_grid(rows=12, cols=12, buff=0).move_to(right_pos)
        
        fine_label = Text("Our Output: 30m", font_size=24, color=TEAL_A).next_to(fine_grid, UP, buff=0.4)

        arrow_out = Arrow(pinn_box.get_right(), fine_grid.get_left(), buff=0.2)
        self.play(Create(arrow_out))

        self.play(Create(fine_grid, lag_ratio=0.01), run_time=2)
        self.play(Write(fine_label))
        self.play(Circumscribe(fine_grid, color=YELLOW, time_width=2))
        self.wait(1.5)

        # ==========================================
        # STEP 4: Side-by-Side Comparison
        # ==========================================
        elements_to_fade = VGroup(pinn_group, arrow_in, arrow_out, sensors, sensor_label, coarse_label, fine_label)
        
        comp_coarse_label = Text("Traditional (9km)", font_size=32, color=BLUE)
        comp_fine_label = Text("Our Network (30m)", font_size=32, color=TEAL_A)
        comparison_title = Text("The Advantage", font_size=40, color=YELLOW).to_edge(UP)

        self.play(FadeOut(elements_to_fade), run_time=1)
        
        # Because they are the exact same size now, scaling them both by 1.2 looks perfectly balanced
        self.play(
            coarse_grid.animate.move_to(LEFT * 2.5).scale(1.2),
            fine_grid.animate.move_to(RIGHT * 2.5).scale(1.2),
            run_time=1.5
        )

        comp_coarse_label.next_to(coarse_grid, DOWN, buff=0.5)
        comp_fine_label.next_to(fine_grid, DOWN, buff=0.5)

        self.play(
            Write(comp_coarse_label),
            Write(comp_fine_label),
            Write(comparison_title),
            run_time=1.5
        )
        self.wait(3)