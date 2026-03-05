import pygame
import random

"""
TODO:
Hold Queue: Allows storing one piece for future use.
Next Queue: Shows the upcoming 5-6 pieces.
7-Bag Randomizer: Ensures a fair distribution, offering all seven pieces in a random order before repeating, preventing long droughts.
Lock Delay: A brief pause when a piece hits the stack, allowing for final adjustments or sliding.
SRS (Super Rotation System): Determines how pieces rotate, including "wall kicks" to nudge pieces into tight spots.
T-Spins: A scoring bonus for rotating a T-piece into a tight, enclosed space, now central to competitive scoring.
Ghost Piece: A silhouette showing where the piece will land.
"""

# ------------------------------------------------------------
# Game configuration and constants
# ------------------------------------------------------------

# Board dimensions in logical cells
GRID_HEIGHT = 20
GRID_WIDTH = 10

# Size and placement of the board in the window (in pixels)
TILE_SIZE = 28
GRID_ORIGIN_X = 60
GRID_ORIGIN_Y = 60

# Frame rate and starting difficulty
FPS = 20
INITIAL_LEVEL = 2

# Horizontal movement repeat timing (in frames)
# How long you must hold before repeat starts, and how often it repeats.
SIDE_INITIAL_DELAY_FRAMES = 6
SIDE_REPEAT_INTERVAL_FRAMES = 2

# Color palette used for pieces (index 0 is background)
COLORS = [
    (0, 0, 0),        # 0 - background / empty
    (123, 50, 169),   # PURPLE 1
    (111, 201, 201),  # CYAN 2
    (233, 202, 16),    # YELLOW 3
    (73, 184, 29),    # GREEN 4
    (232, 65, 57),    # RED 5
    (68, 40, 195),   # BLUE 6
    (255, 153, 2),   # ORANGE 7
]

# Convenience colors for UI text and grid lines
BLACK = (20, 20, 20)
WHITE = (255, 255, 255)
GRAY = (150, 150, 190)


class Figure:
    """
    Represents a single falling Tetris piece.

    The piece shape is described by a 4x4 grid, flattened into indices 0–15.
    `figures` holds all possible shapes and their rotations.
    """
    x = 0
    y = 0

    # Track the last two colors used for any figure so we can avoid them
    last_color = None
    second_last_color = None

    # Track the last used figure type so we can avoid repetition
    last_type = None

    figures = [
        [[1, 5, 9, 13], [4, 5, 6, 7]],
        [[4, 5, 9, 10], [2, 6, 5, 9]],
        [[6, 7, 9, 10], [1, 5, 6, 10]],
        [[1, 2, 5, 9], [0, 4, 5, 6], [1, 5, 9, 8], [4, 5, 6, 10]],
        [[1, 2, 6, 10], [5, 6, 7, 9], [2, 6, 10, 11], [3, 5, 6, 7]],
        [[1, 4, 5, 6], [1, 4, 5, 9], [4, 5, 6, 9], [1, 5, 6, 9]],
        [[1, 2, 5, 6]],
    ]

    def __init__(self, x, y):
        self.x = x
        self.y = y

        #-----------------------------------------------------------
        # Figure type randomizer
        #-----------------------------------------------------------
        # Choose a figure type that is not the last used figure type
        available_types = [
            t
            for t in range(len(self.figures))
            if t != Figure.last_type
        ]
        if not available_types:
            available_types = list(range(len(self.figures)))

        self.type = random.choice(available_types)

        # Update history of last two types
        Figure.last_type = self.type

        #-----------------------------------------------------------
        # Color randomizer
        #-----------------------------------------------------------
        # Choose a color that is not one of the two most recently used
        available_colors = [
            c
            for c in range(1, len(COLORS))
            if c not in (Figure.last_color, Figure.second_last_color)
        ]
        # Fallback: if there are fewer than 1 available (e.g. small palette),
        # allow any non-background color.
        if not available_colors:
            available_colors = list(range(1, len(COLORS)))

        self.color = random.choice(available_colors)

        # Update history of last two colors
        Figure.second_last_color = Figure.last_color
        Figure.last_color = self.color
        self.rotation = 0

    def image(self):
        """
        Return the current shape (4x4 grid flattened to 0–15), normalized so
        that at least one block is always on the top row (row index 0).
        This prevents some pieces from visually spawning starting on the
        second row of the playfield.
        """
        shape = self.figures[self.type][self.rotation]
        # Find the minimum row index among the blocks in this rotation
        min_row = min(idx // 4 for idx in shape)
        if min_row == 0:
            return shape
        offset = min_row * 4
        # Shift all indices up so the topmost blocks are in row 0
        return [idx - offset for idx in shape]

    def rotate(self):
        self.rotation = (self.rotation + 1) % len(self.figures[self.type])


class Tetris:
    """
    Encapsulates the Tetris game state and core game logic.

    The field is a 2D grid of integers where 0 means empty and any positive
    value corresponds to a color index in `COLORS`.
    """

    def __init__(self, height, width):
        # Gameplay state
        self.level = INITIAL_LEVEL
        self.score = 0
        self.state = "start"  # "start" or "gameover"
        self.figure = None
        self.hold_figure = None  # Stored piece for "hold" feature
        self.can_hold = True     # Reset each time a new piece spawns

        # Board configuration
        self.height = height
        self.width = width

        # Screen placement of the board
        self.x = GRID_ORIGIN_X
        self.y = GRID_ORIGIN_Y
        self.zoom = TILE_SIZE

        # 2D grid representing the fixed blocks on the board
        self.field = []
        for i in range(self.height):
            new_line = []
            for _ in range(self.width):
                new_line.append(0)
            self.field.append(new_line)

    def new_figure(self):
        """Spawn a new random piece at the top of the board."""
        self.figure = Figure(3, 0)
        self.can_hold = True

    def intersects(self):
        """
        Check whether the current figure collides with the borders
        of the board or with already placed blocks.
        """
        intersection = False
        for i in range(4):
            for j in range(4):
                if i * 4 + j in self.figure.image():
                    if i + self.figure.y > self.height - 1 or \
                            j + self.figure.x > self.width - 1 or \
                            j + self.figure.x < 0 or \
                            self.field[i + self.figure.y][j + self.figure.x] > 0:
                        intersection = True
        return intersection

    def break_lines(self):
        """
        Scan the board for full lines, remove them, and move
        everything above down. Score grows quadratically with
        the number of cleared lines to reward combos.
        """
        lines = 0
        for i in range(1, self.height):
            zeros = 0
            for j in range(self.width):
                if self.field[i][j] == 0:
                    zeros += 1
            if zeros == 0:
                lines += 1
                for i1 in range(i, 1, -1):
                    for j in range(self.width):
                        self.field[i1][j] = self.field[i1 - 1][j]
        self.score += lines ** 2

    def go_space(self):
        """
        Instantly drop the current piece until it lands and lock it in place.
        """
        while not self.intersects():
            self.figure.y += 1
        self.figure.y -= 1
        self.freeze()

    def go_down(self):
        """
        Move the current piece one cell down and freeze it if it collides.
        """
        self.figure.y += 1
        if self.intersects():
            self.figure.y -= 1
            self.freeze()

    def freeze(self):
        """
        Merge the current piece into the board, clear any full lines,
        and spawn a new piece. If the new piece collides immediately,
        the game is over.
        """
        for i in range(4):
            for j in range(4):
                if i * 4 + j in self.figure.image():
                    self.field[i + self.figure.y][j + self.figure.x] = self.figure.color
        self.break_lines()
        self.new_figure()
        if self.intersects():
            self.state = "gameover"

    def go_side(self, dx):
        """Attempt to move the current piece left or right by `dx` cells."""
        old_x = self.figure.x
        self.figure.x += dx
        if self.intersects():
            self.figure.x = old_x

    def rotate(self):
        """Attempt to rotate the current piece, reverting if it collides."""
        old_rotation = self.figure.rotation
        self.figure.rotate()
        if self.intersects():
            self.figure.rotation = old_rotation

    def hold(self):
        """
        Hold the current piece or swap it with the held one.
        Can only be used once per piece spawn.
        """
        if self.figure is None or not self.can_hold:
            return

        self.can_hold = False

        if self.hold_figure is None:
            # Move current figure into hold and spawn a new one
            self.hold_figure = self.figure
            self.new_figure()
        else:
            # Swap current figure with the held one
            temp = self.figure
            self.figure = self.hold_figure
            self.hold_figure = temp

            # Reset position/rotation for the brought‑in piece
            self.figure.x = 3
            self.figure.y = 0
            self.figure.rotation = 0

            # If it immediately collides, the board is effectively full
            if self.intersects():
                self.state = "gameover"

pygame.init()

# Screen setup
size = (500, 700)
screen = pygame.display.set_mode(size)
pygame.display.set_caption("Tetris")

done = False                    # Main loop flag
clock = pygame.time.Clock()     # Controls frame rate
fps = FPS
game = Tetris(GRID_HEIGHT, GRID_WIDTH)
counter = 0                     # Simple timer to drive automatic falling

pressing_down = False           # True while holding the down arrow
side_direction = 0              # -1 = left, 1 = right, 0 = none
side_hold_frames = 0            # How many frames the current side key has been held

while not done:
    if game.figure is None:
        game.new_figure()
    counter += 1
    if counter > 100000:
        counter = 0

    # Automatic downward movement based on level and FPS.
    if counter % (fps // game.level // 2) == 0 or pressing_down:
        if game.state == "start":
            game.go_down()

    # Handle horizontal auto-repeat while a side key is held.
    if game.state != "gameover" and side_direction != 0:
        side_hold_frames += 1
        if (
            side_hold_frames >= SIDE_INITIAL_DELAY_FRAMES
            and (side_hold_frames - SIDE_INITIAL_DELAY_FRAMES) % SIDE_REPEAT_INTERVAL_FRAMES == 0
        ):
            game.go_side(side_direction)

    # Handle input events (quit, movement, rotation, etc.)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            done = True
        if event.type == pygame.KEYDOWN:
            # Restart the game
            if event.key == pygame.K_ESCAPE:
                game.__init__(20, 10)
            
            #TODO: Optimize this
            if game.state != "gameover":
                # Rotate piece
                if event.key == pygame.K_UP or event.key == pygame.K_TAB:
                    game.rotate()
                # Hold / swap current piece
                if event.key == pygame.K_RETURN:
                    game.hold()
                # Accelerate downward movement while held
                if event.key == pygame.K_DOWN:
                    pressing_down = True
                # Move piece left (start auto-repeat)
                if event.key == pygame.K_LEFT:
                    game.go_side(-1)
                    side_direction = -1
                    side_hold_frames = 0
                # Move piece right (start auto-repeat)
                if event.key == pygame.K_RIGHT:
                    game.go_side(1)
                    side_direction = 1
                    side_hold_frames = 0
                # Hard drop
                if event.key == pygame.K_SPACE:
                    game.go_space()

        if event.type == pygame.KEYUP:
            if event.key == pygame.K_DOWN:
                pressing_down = False
            if event.key == pygame.K_LEFT and side_direction == -1:
                side_direction = 0
                side_hold_frames = 0
            if event.key == pygame.K_RIGHT and side_direction == 1:
                side_direction = 0
                side_hold_frames = 0

    # Clear the screen
    screen.fill(BLACK)

    # Draw fixed blocks; only draw grid lines on empty cells
    for i in range(game.height):
        for j in range(game.width):
            cell_rect = [game.x + game.zoom * j, game.y + game.zoom * i, game.zoom, game.zoom]
            if game.field[i][j] > 0:
                # Filled cell: draw solid block without internal grid lines
                pygame.draw.rect(screen, COLORS[game.field[i][j]], cell_rect)
            else:
                # Empty cell: show grid
                pygame.draw.rect(screen, GRAY, cell_rect, 1)

    # Draw the active falling piece on top of the board
    if game.figure is not None:
        for i in range(4):
            for j in range(4):
                p = i * 4 + j
                if p in game.figure.image():
                    cell_rect = [
                        game.x + game.zoom * (j + game.figure.x),
                        game.y + game.zoom * (i + game.figure.y),
                        game.zoom,
                        game.zoom,
                    ]
                    pygame.draw.rect(screen, COLORS[game.figure.color], cell_rect)

    # Draw a single border around the entire playfield
    pygame.draw.rect(
        screen,
        GRAY,
        [game.x, game.y, game.zoom * game.width, game.zoom * game.height],
        2,
    )

    # ---------------------------------------------
    # Hold area UI (for "hold piece" feature)
    # ---------------------------------------------
    hold_width = TILE_SIZE * 4
    hold_height = TILE_SIZE * 4
    hold_x = game.x + game.zoom * game.width + 30
    hold_y = game.y

    # Outer rectangle for the hold slot
    pygame.draw.rect(
        screen,
        GRAY,
        [hold_x, hold_y, hold_width, hold_height],
        2,
    )

    font = pygame.font.SysFont('Calibri', 25, True, False)
    font1 = pygame.font.SysFont('Calibri', 45, True, False)

    # "HOLD" label above the rectangle
    hold_label = font.render("HOLD", True, WHITE)
    screen.blit(hold_label, (hold_x, hold_y - 26))

    # Draw the held piece (if any) inside the hold area, centered and slightly smaller
    if game.hold_figure is not None:
        shape = game.hold_figure.image()

        # Determine the bounding box of the shape within its 4x4 grid
        rows = [idx // 4 for idx in shape]
        cols = [idx % 4 for idx in shape]
        min_row, max_row = min(rows), max(rows)
        min_col, max_col = min(cols), max(cols)

        # Use a slightly smaller tile size so it fits nicely
        hold_tile = int(TILE_SIZE * 0.8)

        shape_pixel_width = (max_col - min_col + 1) * hold_tile
        shape_pixel_height = (max_row - min_row + 1) * hold_tile

        start_x = hold_x + (hold_width - shape_pixel_width) // 2
        start_y = hold_y + (hold_height - shape_pixel_height) // 2

        for idx in shape:
            row = idx // 4
            col = idx % 4
            cell_rect = [
                start_x + (col - min_col) * hold_tile,
                start_y + (row - min_row) * hold_tile,
                hold_tile,
                hold_tile,
            ]
            pygame.draw.rect(screen, COLORS[game.hold_figure.color], cell_rect)

    # Score and game over UI
    text = font.render("Score: " + str(game.score), True, WHITE)
    text_game_over = font1.render("Game Over", True, WHITE)
    text_game_over1 = font1.render("Press ESC", True, WHITE)

    screen.blit(text, [0, 0])
    if game.state == "gameover":
        screen.blit(text_game_over, [160, 200])
        screen.blit(text_game_over1, [160, 250])

    pygame.display.flip()
    clock.tick(fps)

pygame.quit()